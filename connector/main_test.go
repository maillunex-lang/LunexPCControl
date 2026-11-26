package main

import (
	"context"
	"crypto/ed25519"
	"encoding/base64"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
)

func TestEndpointIsHTTPSAndStrictPath(t *testing.T) {
	valid, err := endpoint("https://rikagro.ru/portalmcp/", "claim")
	if err != nil || valid != "https://rikagro.ru/portalmcp/api/connectors/claim" {
		t.Fatalf("unexpected endpoint: %s %v", valid, err)
	}
	invalid := []string{"http://rikagro.ru/portalmcp/", "https://evil@example.com/portalmcp/",
		"https://rikagro.ru/other/", "https://rikagro.ru/portalmcp/?code=secret",
		"file:///portalmcp"}
	for _, s := range invalid {
		if _, err := endpoint(s, "claim"); err == nil {
			t.Errorf("accepted insecure server %q", s)
		}
	}
}

func TestSecureConfigFileAndOverwriteProtection(t *testing.T) {
	location := filepath.Join(t.TempDir(), "config", "connector.json")
	pub, key, err := ed25519.GenerateKey(nil)
	_ = pub
	if err != nil {
		t.Fatal(err)
	}
	c := config{Version: 1, OS: "linux", DeviceID: strings.Repeat("a", 32), Name: "Ubuntu",
		Server: defaultServer, PrivateKey: base64.URLEncoding.EncodeToString(key)}
	if err := persist(c, location); err != nil {
		t.Fatal(err)
	}
	if err := persist(c, location); err == nil {
		t.Fatal("overwrote owner device identity")
	}
	info, err := os.Stat(location)
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode().Perm()&0077 != 0 {
		t.Fatalf("key file visible to others: %o", info.Mode().Perm())
	}
	saved, priv, err := load(location)
	if err != nil {
		t.Fatal(err)
	}
	if saved.DeviceID != c.DeviceID || !priv.Public().(ed25519.PublicKey).Equal(pub) {
		t.Fatal("saved identity mismatch")
	}
}

func TestHTTPSPairAndSignedHeartbeat(t *testing.T) {
	code := strings.Repeat("Q", 43)
	registered := ed25519.PublicKey(nil)
	id := strings.Repeat("a", 32)
	calls := 0
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" || r.Header.Get("X-LunexPC-Connector") != "v1" {
			t.Error("bad connector headers")
			http.Error(w, "bad", 403)
			return
		}
		var body map[string]any
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Error(err)
			return
		}
		switch r.URL.Path {
		case "/portalmcp/api/connectors/claim":
			if body["pairing_code"] != code || body["os"] != "linux" {
				t.Error("bad claim")
			}
			value, ok := body["public_key"].(string)
			if !ok {
				t.Fatal("public key missing")
			}
			raw, err := base64.URLEncoding.DecodeString(value)
			if err != nil {
				t.Error(err)
			}
			registered = ed25519.PublicKey(raw)
			w.Header().Set("Content-Type", "application/json")
			w.Write([]byte(`{"device_id":"` + id + `","name":"Ubuntu Test","os":"linux"}`))
		case "/portalmcp/api/connectors/heartbeat":
			calls++
			nonce := body["nonce"].(string)
			stamp := int64(body["timestamp"].(float64))
			payload := []byte("LUNEXPC-PRESENCE-v1\n" + id + "\n" + strconv.FormatInt(stamp, 10) + "\n" + nonce + "\n")
			signature, _ := base64.URLEncoding.DecodeString(body["signature"].(string))
			if !ed25519.Verify(registered, payload, signature) {
				t.Error("bad Ed25519 heartbeat signature")
			}
			w.Write([]byte(`{"online":true}`))
		default:
			http.Error(w, "unknown", 404)
		}
	}))
	defer server.Close()
	location := filepath.Join(t.TempDir(), "cfg", "connector.json")
	c, err := pair(context.Background(), server.Client(), server.URL+"/portalmcp/", code, "", "linux", location)
	if err != nil {
		t.Fatal(err)
	}
	if c.DeviceID != id {
		t.Fatal("unexpected paired device ID")
	}
	saved, key, err := load(location)
	if err != nil {
		t.Fatal(err)
	}
	if err := heartbeat(context.Background(), server.Client(), saved, key); err != nil {
		t.Fatal(err)
	}
	if calls != 1 {
		t.Errorf("heartbeat count %d", calls)
	}
	if err := run(context.Background(), server.Client(), saved, key, true); err != nil {
		t.Fatal(err)
	}
	if calls != 2 {
		t.Errorf("heartbeat count %d", calls)
	}
}

func TestClaimDoesNotFollowHTTPRedirect(t *testing.T) {
	redirect := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, "http://example.com/leak", 302)
	}))
	defer redirect.Close()
	client := redirect.Client()
	client.CheckRedirect = func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }
	_, err := pair(context.Background(), client, redirect.URL+"/portalmcp/", strings.Repeat("X", 43), "", "linux", filepath.Join(t.TempDir(), "config"))
	if err == nil {
		t.Fatal("accepted redirect while handling pairing secret")
	}
	if !errors.Is(err, context.DeadlineExceeded) && !strings.Contains(err.Error(), "HTTP 302") {
		t.Fatalf("unexpected redirect error %v", err)
	}
}
