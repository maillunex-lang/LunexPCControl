import unittest
from server.input_policy import validate_input, InputPolicyError, SUPPORTED_INPUT

class InputPolicyTests(unittest.TestCase):
    def test_click_and_move(self):
        self.assertEqual(validate_input("Click", {"loc":[200,400]}),
                         {"loc":[200,400],"button":"left","clicks":1})
        self.assertEqual(validate_input("Move", {"loc":[10,20]}),
                         {"loc":[10,20],"drag":False})
        self.assertEqual(validate_input("Click", {"loc":[0,0],"clicks":0})["clicks"],0)
        for invalid in ({"loc":[1,2],"clicks":3},
                        {"loc":[1,2],"button":"synthesized"},
                        {"loc":[1,2],"label":99},
                        {"loc":[1,2],"drag":True},
                        {"loc":[True,10]}, {"loc":[-1,10]},
                        {"loc":[99999,10]}, {"loc":["1",2]}):
            with self.subTest(args=invalid),self.assertRaises(InputPolicyError):
                validate_input("Click",invalid)
        with self.assertRaises(InputPolicyError):
            validate_input("Move",{"loc":[1,2],"drag":True})

    def test_type_does_not_submit(self):
        allowed=validate_input("Type",{"loc":[123,456],"text":"hello"})
        self.assertEqual(allowed["press_enter"],False)
        self.assertEqual(allowed["caret_position"],"idle")
        self.assertEqual(allowed["clear"],False)
        for invalid in ({"loc":[1,2],"text":"x","press_enter":True},
                        {"loc":[1,2],"text":"x"*501},
                        {"loc":[1,2],"text":""},
                        {"loc":[1,2],"text":4},
                        {"loc":[1,2],"text":"hi","clear":1},
                        {"loc":[1,2],"text":"bad\x00text"}):
            with self.subTest(args=invalid),self.assertRaises(InputPolicyError):
                validate_input("Type",invalid)

    def test_scroll_restricts_units_and_directions(self):
        self.assertEqual(validate_input("Scroll",{"loc":[1,2],"wheel_times":2})["direction"],"down")
        self.assertEqual(validate_input("Scroll",{"loc":[1,2],"type":"horizontal","direction":"left"})["type"],"horizontal")
        for invalid in ({"loc":[1,2],"wheel_times":0},
                        {"loc":[1,2],"wheel_times":99},
                        {"loc":[1,2],"wheel_times":True},
                        {"loc":[1,2],"type":"vertical","direction":"left"},
                        {"loc":[1,2],"type":"horizontal","direction":"up"},
                        {"loc":[1,2],"label":5}):
            with self.subTest(args=invalid),self.assertRaises(InputPolicyError):
                validate_input("Scroll",invalid)

    def test_unsupported_tools(self):
        self.assertEqual(SUPPORTED_INPUT,{"Click","Type","Scroll","Move"})
        for name in ("PowerShell","Shortcut","FileSystem","App","Registry","Kill"):
            with self.subTest(name=name), self.assertRaises(InputPolicyError):
                validate_input(name,{"loc":[1,2]})
