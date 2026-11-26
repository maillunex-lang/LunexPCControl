package main

// Lunex Connector phase 1: owner-approved pairing and signed HTTPS presence.
// This deliberately does not expose a shell, desktop input, open firewall
// ports, start background services or grant MCP privileges.
import (
	"bufio"
	"bytes"
	"context"
	"crypto/ed25519"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"path/filepath"
	"runtime"
	"strings"
	"syscall"
	"time"
)

const defaultServer = "https://rikagro.ru/portalmcp/"
const bodyLimit = 2048

type config struct {
	Version    int    `json:"version"`
	DeviceID   string `json:"device_id"`
	Name       string `json:"name"`
	OS         string `json:"os"`
	Server     string `json:"server"`
	PrivateKey string `json:"private_key"`
}

type claimResult struct {
	DeviceID string `json:"device_id"`
	Name     string `json:"name"`
	OS       string `json:"os"`
}

func endpoint(server, path string) (string, error) {
	u, err := url.Parse(server)
	if err != nil || u.Scheme != "https" || u.Hostname() == "" ||
		u.User != nil || u.RawQuery != "" || u.Fragment != "" || u.Opaque != "" {
		return "", errors.New("HTTPS URL required")
	}
	if strings.TrimRight(u.Path, "/") != "/portalmcp" {
		return "", errors.New("server path must be /portalmcp/")
	}
	return strings.TrimRight(u.String(), "/") + "/api/connectors/" + path, nil
}

func configPath() (string, error) {
	root, err := os.UserConfigDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(root, "LunexPCControl", "connector.json"), nil
}

func persist(c config, location string) error {
	if err := os.MkdirAll(filepath.Dir(location), 0700); err != nil {
		return err
	}
	data, err := json.MarshalIndent(c, "", "  ")
	if err != nil {
		return err
	}
	file, err := os.OpenFile(location, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if err != nil {
		return fmt.Errorf("existing identity is never overwritten: %w", err)
	}
	defer file.Close()
	if _, err = file.Write(data); err != nil {
		return err
	}
	if err = file.Sync(); err != nil {
		return err
	}
	return nil
}

func load(location string) (config, ed25519.PrivateKey, error) {
	var c config
	info, err := os.Lstat(location)
	if err != nil {
		return c, nil, err
	}
	if !info.Mode().IsRegular() {
		return c, nil, errors.New("identity file must be regular")
	}
	if runtime.GOOS != "windows" && info.Mode().Perm()&0077 != 0 {
		return c, nil, errors.New("identity file must be private (0600)")
	}
	data, err := os.ReadFile(location)
	if err != nil {
		return c, nil, err
	}
	if len(data) > 4096 {
		return c, nil, errors.New("identity too large")
	}
	if err = json.Unmarshal(data, &c); err != nil {
		return c, nil, err
	}
	raw, err := base64.URLEncoding.DecodeString(c.PrivateKey)
	if err != nil || len(raw) != ed25519.PrivateKeySize {
		return c, nil, errors.New("invalid identity")
	}
	if c.Version != 1 || len(c.DeviceID) != 32 || (c.OS != "windows" && c.OS != "linux") {
		return c, nil, errors.New("invalid saved identity")
	}
	return c, ed25519.PrivateKey(raw), nil
}

func httpJSON(ctx context.Context, client *http.Client, server, path string, request any, response any) error {
	target, err := endpoint(server, path)
	if err != nil {
		return err
	}
	body, err := json.Marshal(request)
	if err != nil {
		return err
	}
	if len(body) > bodyLimit {
		return errors.New("request exceeds limit")
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, target, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-LunexPC-Connector", "v1")
	res, err := client.Do(req)
	if err != nil {
		return err
	}
	defer res.Body.Close()
	if res.StatusCode != 200 {
		return fmt.Errorf("server rejected request (HTTP %d)", res.StatusCode)
	}
	payload, err := io.ReadAll(io.LimitReader(res.Body, bodyLimit+1))
	if err != nil {
		return err
	}
	if len(payload) > bodyLimit {
		return errors.New("oversized response")
	}
	if err = json.Unmarshal(payload, response); err != nil {
		return err
	}
	return nil
}

func pair(ctx context.Context, client *http.Client, server, code, label, osName, location string) (config, error) {
	if osName != "windows" && osName != "linux" {
		return config{}, errors.New("Windows and Linux only")
	}
	if len(code) < 40 || len(code) > 90 {
		return config{}, errors.New("invalid pairing code")
	}
	_, privateKey, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		return config{}, err
	}
	public := privateKey.Public().(ed25519.PublicKey)
	var result claimResult
	err = httpJSON(ctx, client, server, "claim", map[string]any{
		"pairing_code": code,
		"os":           osName,
		"public_key":   base64.URLEncoding.EncodeToString(public),
	}, &result)
	if err != nil {
		return config{}, err
	}
	if len(result.DeviceID) != 32 || result.OS != osName || result.Name == "" {
		return config{}, errors.New("invalid enrollment response")
	}
	cfg := config{Version: 1, DeviceID: result.DeviceID, Name: result.Name, OS: result.OS,
		Server: server, PrivateKey: base64.URLEncoding.EncodeToString(privateKey)}
	if err = persist(cfg, location); err != nil {
		return config{}, err
	}
	return cfg, nil
}

func heartbeat(ctx context.Context, client *http.Client, c config, privateKey ed25519.PrivateKey) error {
	nonce := make([]byte, 18)
	if _, err := rand.Read(nonce); err != nil {
		return err
	}
	stamp := time.Now().Unix()
	n := base64.RawURLEncoding.EncodeToString(nonce)
	payload := fmt.Sprintf("LUNEXPC-PRESENCE-v1\n%s\n%d\n%s\n", c.DeviceID, stamp, n)
	signature := base64.URLEncoding.EncodeToString(ed25519.Sign(privateKey, []byte(payload)))
	var response struct {
		Online bool `json:"online"`
	}
	if err := httpJSON(ctx, client, c.Server, "heartbeat", map[string]any{
		"device_id": c.DeviceID, "timestamp": stamp, "nonce": n, "signature": signature,
	}, &response); err != nil {
		return err
	}
	if !response.Online {
		return errors.New("invalid heartbeat acknowledgement")
	}
	return nil
}

func run(ctx context.Context, client *http.Client, cfg config, key ed25519.PrivateKey, once bool) error {
	interval := 25 * time.Second
	backoff := 5 * time.Second
	for {
		attemptCtx, cancel := context.WithTimeout(ctx, 15*time.Second)
		err := heartbeat(attemptCtx, client, cfg, key)
		cancel()
		if err == nil {
			fmt.Println("Lunex Connector: online")
			if once {
				return nil
			}
			backoff = 5 * time.Second
		} else {
			fmt.Fprintln(os.Stderr, "Presence unavailable:", err)
			if once {
				return err
			}
		}
		delay := interval
		if err != nil {
			delay = backoff
			backoff *= 2
			if backoff > 120*time.Second {
				backoff = 120 * time.Second
			}
		}
		timer := time.NewTimer(delay)
		select {
		case <-ctx.Done():
			timer.Stop()
			return nil
		case <-timer.C:
		}
	}
}

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "Usage: lunex-connector pair | run | status")
		os.Exit(2)
	}
	action := os.Args[1]
	flags := flag.NewFlagSet(action, flag.ExitOnError)
	server := flags.String("server", defaultServer, "HTTPS portal URL")
	label := flags.String("name", "", "device label shown in portal")
	single := flags.Bool("once", false, "one heartbeat and exit")
	flags.Parse(os.Args[2:])
	location, err := configPath()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	client := &http.Client{Timeout: 20 * time.Second, CheckRedirect: func(req *http.Request, via []*http.Request) error {
		return http.ErrUseLastResponse
	}}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	switch action {
	case "pair":
		if *label != "" {
			fmt.Println("Name is set by the owner in the portal.")
		}
		if _, err = endpoint(*server, "claim"); err != nil {
			break
		}
		if _, err = os.Stat(location); err == nil {
			err = errors.New("device already paired; ask owner to revoke before re-enrollment")
			break
		}
		if !errors.Is(err, os.ErrNotExist) {
			break
		}
		fmt.Print("Enter 10-minute pairing code from the portal: ")
		reader := bufio.NewReader(os.Stdin)
		var code string
		code, err = reader.ReadString('\n')
		if err != nil {
			break
		}
		code = strings.TrimSpace(code)
		var cfg config
		cfg, err = pair(ctx, client, *server, code, "", runtime.GOOS, location)
		if err == nil {
			fmt.Printf("Paired %s (%s). Run: lunex-connector run\n", cfg.Name, cfg.DeviceID)
		}
	case "run":
		var c config
		var key ed25519.PrivateKey
		c, key, err = load(location)
		if err == nil {
			err = run(ctx, client, c, key, *single)
		}
	case "status":
		var c config
		c, _, err = load(location)
		if err == nil {
			fmt.Printf("Device: %s\nID: %s\nOS: %s\nPortal: %s\n", c.Name, c.DeviceID, c.OS, c.Server)
			fmt.Println("This is saved identity metadata, not a live connection check.")
		}
	default:
		err = errors.New("unsupported action; choose pair, run, or status")
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, "Lunex Connector:", err)
		os.Exit(1)
	}
}
