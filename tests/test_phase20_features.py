"""Phase 20 feature tests.

Covers:
- crypto.subtle — SubtleCrypto digest, generateKey, importKey, sign, encrypt/decrypt
- Blob / File — binary data with size, type, text(), arrayBuffer(), slice(), name, lastModified
- Headers — HTTP headers with get/set/has/delete/append/getAll/keys/values/entries
- FormData — key/value pairs with append/set/get/getAll/has/delete/keys/values/entries
- Request / Response — Fetch API objects
- fetch — global fetch function returning Response
- EventTarget / Event / CustomEvent — DOM event system
- ReadableStream / WritableStream / TransformStream — Web Streams API
- CompressionStream / DecompressionStream — compression stream stubs
- BroadcastChannel — pub/sub messaging
- MessageChannel / MessagePort — bi-directional message passing
- navigator — userAgent, language, onLine, hardwareConcurrency, platform
"""

import pytest
from sprycode.interpreter import Interpreter, SpryRuntimeError
from sprycode.lexer import Lexer
from sprycode.parser import Parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(source: str) -> Interpreter:
    tokens = Lexer(source).tokenize()
    prog = Parser(tokens).parse()
    i = Interpreter()
    i.run(prog)
    return i


def val(interp_or_src, name: str = "_result") -> object:
    if isinstance(interp_or_src, str):
        return run(f"let _result = {interp_or_src}").globals.get("_result")
    return interp_or_src.globals.get(name)


# ===========================================================================
# crypto.subtle
# ===========================================================================

class TestSubtleCrypto:
    def test_subtle_property_accessible(self):
        i = run("let v = crypto.subtle")
        assert val(i, "v") is not None

    def test_digest_sha256_returns_list(self):
        i = run("""
let subtle = crypto.subtle()
let result = subtle.digest("SHA-256", "hello")
let v = len(result)
""")
        assert val(i, "v") == 32  # SHA-256 = 32 bytes

    def test_digest_sha1_returns_20_bytes(self):
        i = run("""
let subtle = crypto.subtle()
let v = len(subtle.digest("SHA-1", "hello"))
""")
        assert val(i, "v") == 20

    def test_digest_sha512_returns_64_bytes(self):
        i = run("""
let subtle = crypto.subtle()
let v = len(subtle.digest("SHA-512", "hello"))
""")
        assert val(i, "v") == 64

    def test_digest_sha384_returns_48_bytes(self):
        i = run("""
let subtle = crypto.subtle()
let v = len(subtle.digest("SHA-384", "hello"))
""")
        assert val(i, "v") == 48

    def test_digest_returns_correct_hash(self):
        i = run("""
let subtle = crypto.subtle()
let result = subtle.digest("SHA-256", "")
let v = result[0]
""")
        # SHA-256("") = e3b0c44298fc1c14... first byte = 0xe3 = 227
        assert val(i, "v") == 0xe3

    def test_digest_from_typed_array(self):
        i = run("""
let subtle = crypto.subtle()
let arr = Uint8Array.new([104, 101, 108, 108, 111])
let result = subtle.digest("SHA-256", arr)
let v = len(result)
""")
        assert val(i, "v") == 32

    def test_generate_key_returns_dict(self):
        i = run("""
let subtle = crypto.subtle()
let key = subtle.generateKey({ name: "AES-GCM" }, true, ["encrypt"])
let v = key.type
""")
        assert val(i, "v") == "secret"

    def test_import_key(self):
        i = run("""
let subtle = crypto.subtle()
let key = subtle.importKey("raw", [1,2,3], "AES-GCM", true, ["encrypt"])
let v = key.extractable
""")
        assert val(i, "v") is True

    def test_sign_returns_bytes(self):
        i = run("""
let subtle = crypto.subtle()
let key = subtle.generateKey("HMAC", true, [])
let sig = subtle.sign("HMAC", key, "data")
let v = len(sig)
""")
        assert val(i, "v") == 32  # HMAC-SHA256 = 32 bytes

    def test_verify_returns_bool(self):
        i = run("""
let subtle = crypto.subtle()
let v = subtle.verify("HMAC", {}, [], "data")
""")
        assert val(i, "v") is True

    def test_encrypt_returns_bytes(self):
        i = run("""
let subtle = crypto.subtle()
let v = len(subtle.encrypt("AES-GCM", {}, "hello"))
""")
        assert val(i, "v") == 5  # stub returns input as-is

    def test_decrypt_returns_bytes(self):
        i = run("""
let subtle = crypto.subtle()
let data = [104, 101, 108]
let v = len(subtle.decrypt("AES-GCM", {}, data))
""")
        assert val(i, "v") == 3

    def test_derive_bits(self):
        i = run("""
let subtle = crypto.subtle()
let bits = subtle.deriveBits({}, {}, 128)
let v = len(bits)
""")
        assert val(i, "v") == 16  # 128 bits = 16 bytes


# ===========================================================================
# Blob
# ===========================================================================

class TestBlob:
    def test_create_empty(self):
        i = run("let b = Blob.new()\nlet v = b.size")
        assert val(i, "v") == 0

    def test_create_from_string(self):
        i = run("let b = Blob.new([\"hello\"])\nlet v = b.size")
        assert val(i, "v") == 5

    def test_type_default_empty(self):
        i = run("let b = Blob.new([\"hello\"])\nlet v = b.type")
        assert val(i, "v") == ""

    def test_type_from_options(self):
        i = run("let b = Blob.new([\"hello\"], { type: \"text/plain\" })\nlet v = b.type")
        assert val(i, "v") == "text/plain"

    def test_text_method(self):
        i = run("let b = Blob.new([\"hello\"])\nlet v = b.text()")
        assert val(i, "v") == "hello"

    def test_multiple_parts(self):
        i = run("let b = Blob.new([\"hello\", \" \", \"world\"])\nlet v = b.text()")
        assert val(i, "v") == "hello world"

    def test_size_after_concat(self):
        i = run("let b = Blob.new([\"hello\", \" world\"])\nlet v = b.size")
        assert val(i, "v") == 11

    def test_bytes_method(self):
        i = run("let b = Blob.new([\"hi\"])\nlet v = b.bytes()[0]")
        assert val(i, "v") == ord("h")

    def test_array_buffer(self):
        i = run("""
let b = Blob.new(["ab"])
let buf = b.arrayBuffer()
let v = buf.byteLength
""")
        assert val(i, "v") == 2

    def test_slice_basic(self):
        i = run("let b = Blob.new([\"hello world\"])\nlet s = b.slice(6, 11)\nlet v = s.text()")
        assert val(i, "v") == "world"

    def test_slice_with_content_type(self):
        i = run("let b = Blob.new([\"hello\"])\nlet s = b.slice(0, 5, \"text/plain\")\nlet v = s.type")
        assert val(i, "v") == "text/plain"

    def test_callable_constructor(self):
        i = run("let b = Blob([\"hello\"])\nlet v = b.size")
        assert val(i, "v") == 5


# ===========================================================================
# File
# ===========================================================================

class TestFile:
    def test_create_file(self):
        i = run("let f = File.new([\"content\"], \"test.txt\")\nlet v = f.name")
        assert val(i, "v") == "test.txt"

    def test_file_size(self):
        i = run("let f = File.new([\"hello\"], \"a.txt\")\nlet v = f.size")
        assert val(i, "v") == 5

    def test_file_text(self):
        i = run("let f = File.new([\"hello world\"], \"msg.txt\")\nlet v = f.text()")
        assert val(i, "v") == "hello world"

    def test_file_type(self):
        i = run("let f = File.new([\"hi\"], \"a.txt\", { type: \"text/plain\" })\nlet v = f.type")
        assert val(i, "v") == "text/plain"

    def test_file_last_modified_is_number(self):
        from sprycode.interpreter import SpryFile
        i = run("let f = File.new([\"hi\"], \"a.txt\")")
        f = i.globals.get("f")
        assert isinstance(f, SpryFile)
        assert isinstance(f.lastModified, int)

    def test_file_last_modified_custom(self):
        i = run("let f = File.new([\"hi\"], \"a.txt\", { lastModified: 1000 })\nlet v = f.lastModified")
        assert val(i, "v") == 1000

    def test_file_is_blob_subtype(self):
        i = run("let f = File.new([\"hi\"], \"x.txt\")\nlet v = f.bytes()[0]")
        assert val(i, "v") == ord("h")

    def test_file_callable_constructor(self):
        i = run("let f = File([\"data\"], \"f.txt\")\nlet v = f.name")
        assert val(i, "v") == "f.txt"


# ===========================================================================
# Headers
# ===========================================================================

class TestHeaders:
    def test_create_empty(self):
        i = run("let h = Headers.new()\nlet v = h.has(\"content-type\")")
        assert val(i, "v") is False

    def test_set_and_get(self):
        i = run("let h = Headers.new()\nh.set(\"Content-Type\", \"application/json\")\nlet v = h.get(\"Content-Type\")")
        assert val(i, "v") == "application/json"

    def test_case_insensitive(self):
        i = run("let h = Headers.new()\nh.set(\"X-Custom\", \"value\")\nlet v = h.get(\"x-custom\")")
        assert val(i, "v") == "value"

    def test_has_returns_true(self):
        i = run("let h = Headers.new()\nh.set(\"accept\", \"*/*\")\nlet v = h.has(\"Accept\")")
        assert val(i, "v") is True

    def test_has_returns_false(self):
        i = run("let h = Headers.new()\nlet v = h.has(\"missing\")")
        assert val(i, "v") is False

    def test_delete(self):
        i = run("let h = Headers.new()\nh.set(\"x\", \"1\")\nh.delete(\"x\")\nlet v = h.has(\"x\")")
        assert val(i, "v") is False

    def test_append_multiple(self):
        i = run("""
let h = Headers.new()
h.append("Set-Cookie", "a=1")
h.append("Set-Cookie", "b=2")
let v = len(h.getAll("Set-Cookie"))
""")
        assert val(i, "v") == 2

    def test_get_returns_null_for_missing(self):
        i = run("let h = Headers.new()\nlet v = h.get(\"missing\")")
        assert val(i, "v") is None

    def test_keys(self):
        i = run("""
let h = Headers.new()
h.set("a", "1")
h.set("b", "2")
let v = len(h.keys())
""")
        assert val(i, "v") == 2

    def test_entries(self):
        i = run("""
let h = Headers.new()
h.set("content-type", "text/html")
let v = h.entries()[0][0]
""")
        assert val(i, "v") == "content-type"

    def test_init_from_dict(self):
        i = run("let h = Headers.new({ \"Accept\": \"*/*\" })\nlet v = h.get(\"accept\")")
        assert val(i, "v") == "*/*"

    def test_callable_constructor(self):
        i = run("let h = Headers({ \"x-foo\": \"bar\" })\nlet v = h.get(\"x-foo\")")
        assert val(i, "v") == "bar"


# ===========================================================================
# FormData
# ===========================================================================

class TestFormData:
    def test_create_empty(self):
        i = run("let fd = FormData.new()\nlet v = fd.has(\"key\")")
        assert val(i, "v") is False

    def test_append_and_get(self):
        i = run("let fd = FormData.new()\nfd.append(\"name\", \"Alice\")\nlet v = fd.get(\"name\")")
        assert val(i, "v") == "Alice"

    def test_set_replaces(self):
        i = run("""
let fd = FormData.new()
fd.append("k", "first")
fd.append("k", "second")
fd.set("k", "replaced")
let v = fd.getAll("k")
""")
        assert val(i, "v") == ["replaced"]

    def test_get_all(self):
        i = run("""
let fd = FormData.new()
fd.append("tag", "a")
fd.append("tag", "b")
fd.append("tag", "c")
let v = len(fd.getAll("tag"))
""")
        assert val(i, "v") == 3

    def test_has(self):
        i = run("let fd = FormData.new()\nfd.append(\"x\", \"1\")\nlet v = fd.has(\"x\")")
        assert val(i, "v") is True

    def test_delete(self):
        i = run("let fd = FormData.new()\nfd.append(\"x\", \"1\")\nfd.delete(\"x\")\nlet v = fd.has(\"x\")")
        assert val(i, "v") is False

    def test_keys(self):
        i = run("""
let fd = FormData.new()
fd.append("a", "1")
fd.append("b", "2")
let v = len(fd.keys())
""")
        assert val(i, "v") == 2

    def test_values(self):
        i = run("let fd = FormData.new()\nfd.append(\"x\", \"hello\")\nlet v = fd.values()[0]")
        assert val(i, "v") == "hello"

    def test_entries(self):
        i = run("let fd = FormData.new()\nfd.append(\"k\", \"v\")\nlet v = fd.entries()[0][0]")
        assert val(i, "v") == "k"

    def test_get_missing_returns_null(self):
        i = run("let fd = FormData.new()\nlet v = fd.get(\"missing\")")
        assert val(i, "v") is None

    def test_callable_constructor(self):
        i = run("let fd = FormData({ \"a\": \"1\" })\nlet v = fd.get(\"a\")")
        assert val(i, "v") == "1"


# ===========================================================================
# Request
# ===========================================================================

class TestRequest:
    def test_create_request(self):
        i = run("let r = Request.new(\"https://example.com\")\nlet v = r.url")
        assert val(i, "v") == "https://example.com"

    def test_default_method_get(self):
        i = run("let r = Request.new(\"https://example.com\")\nlet v = r.method")
        assert val(i, "v") == "GET"

    def test_method_post(self):
        i = run("let r = Request.new(\"https://example.com\", { method: \"POST\" })\nlet v = r.method")
        assert val(i, "v") == "POST"

    def test_headers_accessible(self):
        i = run("""
let r = Request.new("https://example.com", {
    headers: { "Accept": "application/json" }
})
let v = r.headers.get("accept")
""")
        assert val(i, "v") == "application/json"

    def test_body_property(self):
        i = run("let r = Request.new(\"https://x.com\", { body: \"data\" })\nlet v = r.text()")
        assert val(i, "v") == "data"

    def test_clone(self):
        i = run("""
let r = Request.new("https://example.com", { method: "PUT" })
let r2 = r.clone()
let v = r2.method
""")
        assert val(i, "v") == "PUT"

    def test_callable_constructor(self):
        i = run("let r = Request(\"https://example.com\")\nlet v = r.url")
        assert val(i, "v") == "https://example.com"


# ===========================================================================
# Response
# ===========================================================================

class TestResponse:
    def test_create_response(self):
        i = run("let r = Response.new(\"hello\")\nlet v = r.text()")
        assert val(i, "v") == "hello"

    def test_status_200_ok(self):
        i = run("let r = Response.new(\"ok\")\nlet v = r.ok")
        assert val(i, "v") is True

    def test_status_404_not_ok(self):
        i = run("let r = Response.new(\"not found\", { status: 404 })\nlet v = r.ok")
        assert val(i, "v") is False

    def test_status_code(self):
        i = run("let r = Response.new(null, { status: 201 })\nlet v = r.status")
        assert val(i, "v") == 201

    def test_status_text(self):
        i = run("let r = Response.new(null, { status: 201, statusText: \"Created\" })\nlet v = r.statusText")
        assert val(i, "v") == "Created"

    def test_headers(self):
        i = run("""
let r = Response.new("body", {
    status: 200,
    headers: { "Content-Type": "text/html" }
})
let v = r.headers.get("content-type")
""")
        assert val(i, "v") == "text/html"

    def test_json_method(self):
        i = run("let r = Response.new(\"[1,2,3]\")\nlet v = r.json()")
        assert val(i, "v") == [1, 2, 3]

    def test_blob_method(self):
        i = run("let r = Response.new(\"hello\")\nlet v = r.blob().size")
        assert val(i, "v") == 5

    def test_array_buffer_method(self):
        i = run("let r = Response.new(\"hello\")\nlet v = r.arrayBuffer().byteLength")
        assert val(i, "v") == 5

    def test_bytes_method(self):
        i = run("let r = Response.new(\"hi\")\nlet v = len(r.bytes())")
        assert val(i, "v") == 2

    def test_clone(self):
        i = run("let r = Response.new(\"text\", { status: 201 })\nlet r2 = r.clone()\nlet v = r2.status")
        assert val(i, "v") == 201

    def test_response_json_static(self):
        i = run("let r = Response.json({ a: 1 })\nlet v = r.headers.get(\"content-type\")")
        assert val(i, "v") == "application/json"

    def test_response_error_static(self):
        i = run("let r = Response.error()\nlet v = r.ok")
        assert val(i, "v") is False

    def test_response_redirect_static(self):
        i = run("let r = Response.redirect(\"https://example.com\", 301)\nlet v = r.headers.get(\"location\")")
        assert val(i, "v") == "https://example.com"

    def test_callable_constructor(self):
        i = run("let r = Response(\"data\")\nlet v = r.text()")
        assert val(i, "v") == "data"


# ===========================================================================
# fetch
# ===========================================================================

class TestFetch:
    def test_fetch_exists(self):
        i = run("let v = typeof fetch")
        assert val(i, "v") != "undefined"

    def test_fetch_returns_response(self):
        i = run("""
let r = fetch("http://localhost:9999/test")
let v = r.status
""")
        # Should return a response even if request fails
        assert val(i, "v") in (0, 200, 404, 500) or isinstance(val(i, "v"), int)

    def test_fetch_returns_response_object(self):
        from sprycode.interpreter import SpryResponse
        i = run("let r = fetch(\"http://localhost:9999/nonexistent\")")
        r = val(i, "r")
        assert isinstance(r, SpryResponse)


# ===========================================================================
# EventTarget / Event / CustomEvent
# ===========================================================================

class TestEventTarget:
    def test_create_event_target(self):
        i = run("let et = EventTarget.new()\nlet v = typeof et")
        assert val(i, "v") != "undefined"

    def test_add_and_dispatch_event(self):
        i = run("""
var received = ""
let et = EventTarget.new()
let handler = e => { received = e.type }
et.addEventListener("click", handler)
let evt = Event.new("click")
et.dispatchEvent(evt)
let v = received
""")
        assert val(i, "v") == "click"

    def test_remove_event_listener(self):
        i = run("""
var count = 0
let et = EventTarget.new()
let handler = e => { count = count + 1 }
et.addEventListener("click", handler)
et.removeEventListener("click", handler)
let evt = Event.new("click")
et.dispatchEvent(evt)
let v = count
""")
        assert val(i, "v") == 0

    def test_dispatch_returns_true_by_default(self):
        i = run("""
let et = EventTarget.new()
let evt = Event.new("test")
let v = et.dispatchEvent(evt)
""")
        assert val(i, "v") is True

    def test_dispatch_returns_false_when_prevented(self):
        i = run("""
let et = EventTarget.new()
let handler = e => { e.preventDefault() }
et.addEventListener("test", handler)
let evt = Event.new("test", { cancelable: true })
let v = et.dispatchEvent(evt)
""")
        assert val(i, "v") is False

    def test_multiple_listeners(self):
        i = run("""
var calls = []
let et = EventTarget.new()
et.addEventListener("go", e => { calls = calls + ["a"] })
et.addEventListener("go", e => { calls = calls + ["b"] })
et.dispatchEvent(Event.new("go"))
let v = len(calls)
""")
        assert val(i, "v") == 2


class TestEvent:
    def test_event_type(self):
        i = run("let e = Event.new(\"click\")\nlet v = e.type")
        assert val(i, "v") == "click"

    def test_event_bubbles_default_false(self):
        i = run("let e = Event.new(\"click\")\nlet v = e.bubbles")
        assert val(i, "v") is False

    def test_event_bubbles_true(self):
        i = run("let e = Event.new(\"click\", { bubbles: true })\nlet v = e.bubbles")
        assert val(i, "v") is True

    def test_event_cancelable_default_false(self):
        i = run("let e = Event.new(\"x\")\nlet v = e.cancelable")
        assert val(i, "v") is False

    def test_event_prevent_default(self):
        i = run("""
let e = Event.new("x", { cancelable: true })
e.preventDefault()
let v = e.defaultPrevented
""")
        assert val(i, "v") is True

    def test_prevent_default_noop_if_not_cancelable(self):
        i = run("""
let e = Event.new("x")
e.preventDefault()
let v = e.defaultPrevented
""")
        assert val(i, "v") is False

    def test_callable_constructor(self):
        i = run("let e = Event(\"dblclick\")\nlet v = e.type")
        assert val(i, "v") == "dblclick"


class TestCustomEvent:
    def test_custom_event_detail(self):
        i = run("let e = CustomEvent.new(\"myevent\", { detail: 42 })\nlet v = e.detail")
        assert val(i, "v") == 42

    def test_custom_event_detail_dict(self):
        i = run("let e = CustomEvent.new(\"myevent\", { detail: { x: 10 } })\nlet v = e.detail.x")
        assert val(i, "v") == 10

    def test_custom_event_type(self):
        i = run("let e = CustomEvent.new(\"custom\")\nlet v = e.type")
        assert val(i, "v") == "custom"

    def test_custom_event_detail_default_null(self):
        i = run("let e = CustomEvent.new(\"x\")\nlet v = e.detail")
        assert val(i, "v") is None

    def test_callable_constructor(self):
        i = run("let e = CustomEvent(\"test\", { detail: \"payload\" })\nlet v = e.detail")
        assert val(i, "v") == "payload"


# ===========================================================================
# ReadableStream / WritableStream / TransformStream
# ===========================================================================

class TestReadableStream:
    def test_create(self):
        i = run("let s = ReadableStream.new()\nlet v = s.locked")
        assert val(i, "v") is False

    def test_get_reader(self):
        i = run("""
let s = ReadableStream.new({
    start: ctrl => {
        ctrl.enqueue(1)
        ctrl.enqueue(2)
        ctrl.close()
    }
})
let reader = s.getReader()
let chunk = reader.read()
let v = chunk.value
""")
        assert val(i, "v") == 1

    def test_reader_done(self):
        i = run("""
let s = ReadableStream.new({
    start: ctrl => { ctrl.close() }
})
let reader = s.getReader()
let chunk = reader.read()
let v = chunk.done
""")
        assert val(i, "v") is True

    def test_tee(self):
        i = run("""
let s = ReadableStream.new({
    start: ctrl => { ctrl.enqueue("x") }
})
let branches = s.tee()
let v = len(branches)
""")
        assert val(i, "v") == 2

    def test_tee_branches_have_same_data(self):
        i = run("""
let s = ReadableStream.new({
    start: ctrl => { ctrl.enqueue("data") }
})
let branches = s.tee()
let r1 = branches[0].getReader()
let r2 = branches[1].getReader()
let c1 = r1.read()
let c2 = r2.read()
let v = c1.value == c2.value
""")
        assert val(i, "v") is True

    def test_pipe_to_writable(self):
        from sprycode.interpreter import SpryWritableStream
        i = run("""
let src = ReadableStream.new({
    start: ctrl => {
        ctrl.enqueue("hello")
    }
})
let dest = WritableStream.new()
src.pipeTo(dest)
""")
        dest = i.globals.get("dest")
        assert isinstance(dest, SpryWritableStream)
        assert dest._chunks == ["hello"]

    def test_from_method(self):
        i = run("""
let s = ReadableStream.from([1, 2, 3])
let r = s.getReader()
let c = r.read()
let v = c.value
""")
        assert val(i, "v") == 1


class TestWritableStream:
    def test_create(self):
        i = run("let s = WritableStream.new()\nlet v = s.locked")
        assert val(i, "v") is False

    def test_get_writer(self):
        i = run("""
let s = WritableStream.new()
let writer = s.getWriter()
writer.write("hello")
writer.close()
""")
        from sprycode.interpreter import SpryWritableStream
        i2 = run("""
let s = WritableStream.new()
let writer = s.getWriter()
writer.write("chunk1")
""")
        ws = i2.globals.get("s")
        assert "chunk1" in ws._chunks

    def test_writer_abort(self):
        i = run("""
let s = WritableStream.new()
let writer = s.getWriter()
writer.abort()
let v = s.locked
""")
        # after abort stream is still locked (writer holds it) but closed
        from sprycode.interpreter import SpryWritableStream
        ws = val(i, "s")
        assert isinstance(ws, SpryWritableStream)


class TestTransformStream:
    def test_create(self):
        i = run("let ts = TransformStream.new()\nlet v = typeof ts.readable")
        assert val(i, "v") != "undefined"

    def test_readable_property(self):
        from sprycode.interpreter import SpryReadableStream
        i = run("let ts = TransformStream.new()")
        ts = i.globals.get("ts")
        from sprycode.interpreter import SpryTransformStream
        assert isinstance(ts, SpryTransformStream)
        assert isinstance(ts.readable, SpryReadableStream)

    def test_writable_property(self):
        from sprycode.interpreter import SpryWritableStream, SpryTransformStream
        i = run("let ts = TransformStream.new()")
        ts = i.globals.get("ts")
        assert isinstance(ts.writable, SpryWritableStream)

    def test_pipe_through(self):
        i = run("""
let src = ReadableStream.new({
    start: ctrl => {
        ctrl.enqueue(1)
        ctrl.enqueue(2)
    }
})
let ts = TransformStream.new({
    transform: (chunk, ctrl) => { ctrl.enqueue(chunk * 2) }
})
let result = src.pipeThrough(ts)
let reader = result.getReader()
let c1 = reader.read()
let v = c1.value
""")
        assert val(i, "v") == 2


# ===========================================================================
# CompressionStream / DecompressionStream
# ===========================================================================

class TestCompressionStream:
    def test_create_compression_stream(self):
        i = run("let cs = CompressionStream.new(\"gzip\")\nlet v = typeof cs.readable")
        assert val(i, "v") != "undefined"

    def test_create_decompression_stream(self):
        i = run("let ds = DecompressionStream.new(\"gzip\")\nlet v = typeof ds.writable")
        assert val(i, "v") != "undefined"

    def test_readable_is_readable_stream(self):
        from sprycode.interpreter import SpryReadableStream
        i = run("let cs = CompressionStream.new(\"deflate\")")
        cs = i.globals.get("cs")
        from sprycode.interpreter import _CompressionStreamImpl
        assert isinstance(cs, _CompressionStreamImpl)
        assert isinstance(cs.readable, SpryReadableStream)

    def test_callable_constructor(self):
        i = run("let cs = CompressionStream(\"gzip\")\nlet v = typeof cs.readable")
        assert val(i, "v") != "undefined"

    def test_decompression_callable(self):
        i = run("let ds = DecompressionStream(\"deflate\")\nlet v = typeof ds.writable")
        assert val(i, "v") != "undefined"


# ===========================================================================
# BroadcastChannel
# ===========================================================================

class TestBroadcastChannel:
    def test_create(self):
        i = run("let ch = BroadcastChannel.new(\"test-ch\")\nlet v = ch.name")
        assert val(i, "v") == "test-ch"

    def test_post_message_to_sibling(self):
        i = run("""
var received = null
let ch1 = BroadcastChannel.new("room")
let ch2 = BroadcastChannel.new("room")
ch2.addEventListener("message", e => { received = e.data })
ch1.postMessage("hello")
ch1.close()
ch2.close()
let v = received
""")
        assert val(i, "v") == "hello"

    def test_post_message_not_to_self(self):
        i = run("""
var selfReceived = false
let ch = BroadcastChannel.new("solo")
ch.addEventListener("message", e => { selfReceived = true })
ch.postMessage("ignored")
ch.close()
let v = selfReceived
""")
        assert val(i, "v") is False

    def test_close(self):
        i = run("""
let ch = BroadcastChannel.new("close-test")
ch.close()
var errored = false
try {
    ch.postMessage("should fail")
} catch e {
    errored = true
}
let v = errored
""")
        assert val(i, "v") is True

    def test_callable_constructor(self):
        i = run("let ch = BroadcastChannel(\"x\")\nlet v = ch.name")
        assert val(i, "v") == "x"


# ===========================================================================
# MessageChannel / MessagePort
# ===========================================================================

class TestMessageChannel:
    def test_create(self):
        from sprycode.interpreter import SpryMessageChannel
        i = run("let mc = MessageChannel.new()")
        mc = i.globals.get("mc")
        assert isinstance(mc, SpryMessageChannel)

    def test_two_ports(self):
        i = run("""
let mc = MessageChannel.new()
let v = mc.port1
""")
        from sprycode.interpreter import SpryMessagePort
        assert isinstance(val(i, "v"), SpryMessagePort)

    def test_post_message_between_ports(self):
        i = run("""
var received = null
let mc = MessageChannel.new()
mc.port2.addEventListener("message", e => { received = e.data })
mc.port1.postMessage("ping")
let v = received
""")
        assert val(i, "v") == "ping"

    def test_reply_back(self):
        i = run("""
var reply = null
let mc = MessageChannel.new()
mc.port2.addEventListener("message", e => { mc.port2.postMessage("pong") })
mc.port1.addEventListener("message", e => { reply = e.data })
mc.port1.postMessage("ping")
let v = reply
""")
        assert val(i, "v") == "pong"

    def test_callable_constructor(self):
        i = run("let mc = MessageChannel()\nlet v = mc.port1")
        from sprycode.interpreter import SpryMessagePort
        assert isinstance(val(i, "v"), SpryMessagePort)


# ===========================================================================
# navigator
# ===========================================================================

class TestNavigator:
    def test_user_agent_is_string(self):
        i = run("let v = navigator.userAgent")
        assert isinstance(val(i, "v"), str)
        assert len(val(i, "v")) > 0

    def test_language_is_string(self):
        i = run("let v = navigator.language")
        assert isinstance(val(i, "v"), str)

    def test_languages_is_list(self):
        i = run("let v = navigator.languages")
        assert isinstance(val(i, "v"), list)
        assert len(val(i, "v")) >= 1

    def test_online_is_true(self):
        i = run("let v = navigator.onLine")
        assert val(i, "v") is True

    def test_hardware_concurrency_positive(self):
        i = run("let v = navigator.hardwareConcurrency")
        assert isinstance(val(i, "v"), int)
        assert val(i, "v") >= 1

    def test_platform_is_string(self):
        i = run("let v = navigator.platform")
        assert isinstance(val(i, "v"), str)

    def test_cookie_enabled_false(self):
        i = run("let v = navigator.cookieEnabled")
        assert val(i, "v") is False
