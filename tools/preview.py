#!/usr/bin/env python3
"""Preview the same Jekyll source files without a Ruby installation.

    python tools/preview.py --build
    python tools/preview.py --port 8765

Dependencies live in tools/.deps. Liquid and SCSS are rendered by python-liquid
and libsass; Markdown uses Mistune rather than Kramdown. This is a preview tool,
not a replacement for the GitHub Pages/Jekyll build or its plugins. It supports
front matter, page defaults, YAML data, layouts, includes, URL filters, and
redirect_from. All generated files stay in _site.
"""

import sys

# Importing the locally installed dependencies must not create source-tree files.
sys.dont_write_bytecode = True

from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "_site"
sys.path.insert(0, str(ROOT / "tools" / ".deps"))

try:
    import liquid
    import mistune
    import sass
    import yaml
    from liquid.loader import TemplateSource
except ImportError as exc:
    raise SystemExit(
        "Missing preview dependency: {}\n"
        "Install the local dependencies with:\n"
        "python -m pip install --target tools/.deps "
        "-r tools/requirements-preview.txt".format(exc)
    )

import argparse
import fnmatch
import hashlib
import html
import json
import mimetypes
import os
import re
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Optional, Set, Tuple
from urllib.parse import unquote, urlsplit, urlunsplit

SOURCE_DIRS = ("_pages", "_data", "_layouts", "_includes", "_sass",
               "assets", "images", "files")
STATIC_DIRS = ("assets", "images", "files")
REVISION_ENDPOINT = "/__preview_revision__"
INCLUDE_NAME = re.compile(r"({%-?\s*include\s+)([A-Za-z0-9_./-]+)(?=\s|[-]?%})")
FRONT_MATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)^(?:---|\.\.\.)[ \t]*(?:\r?\n|\Z)", re.S | re.M)


def within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def source_path(relative: str) -> Path:
    path = ROOT / relative
    if not within(path.resolve(), ROOT):
        raise ValueError("Source path escapes the homepage directory: " + relative)
    return path


def walk_files(directory: Path, skip_hidden: bool = True):
    """Walk one permitted directory without following links or junctions."""
    if not directory.exists():
        return
    if directory.is_symlink() or not within(directory.resolve(), ROOT):
        raise ValueError("Linked source/output directories are not supported: " + str(directory))
    for current, directories, files in os.walk(str(directory), followlinks=False):
        current_path = Path(current)
        for name in list(directories):
            child = current_path / name
            if child.is_symlink() or not within(child.resolve(), directory.resolve()):
                raise ValueError("Linked directories are not supported: " + str(child))
            if skip_hidden and name.startswith("."):
                directories.remove(name)
        for name in files:
            path = current_path / name
            if path.is_symlink() or not within(path.resolve(), directory.resolve()):
                raise ValueError("Linked files are not supported: " + str(path))
            if not skip_hidden or not name.startswith("."):
                yield path


def read_yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Expected a YAML mapping in " + str(path.relative_to(ROOT)))
    return value


def split_front_matter(text: str, name: str) -> Tuple[dict, str]:
    match = FRONT_MATTER.match(text)
    if match is None:
        if text.startswith("---\n") or text.startswith("---\r\n"):
            raise ValueError("Unclosed front matter in " + name)
        return {}, text
    data = yaml.safe_load(match.group(1)) or {}
    if not isinstance(data, dict):
        raise ValueError("Expected a front-matter mapping in " + name)
    return data, text[match.end():]


def preprocess_includes(text: str) -> str:
    # Jekyll accepts include head.html; Liquid expects include 'head.html'.
    return INCLUDE_NAME.sub(lambda match: match.group(1) + "'" + match.group(2) + "'", text)


class JekyllIncludeLoader(liquid.FileSystemLoader):
    def get_source(self, env, template_name, *, context=None, **kwargs):
        source = super().get_source(env, template_name, context=context, **kwargs)
        return TemplateSource(preprocess_includes(source.text), source.name,
                              source.uptodate, source.matter)


def base_url(value) -> str:
    value = str(value or "").strip().strip("/")
    if not value:
        return ""
    if any(part in (".", "..", "") for part in value.split("/")) or any(c in value for c in "\\?#:"):
        raise ValueError("baseurl must be a site path such as /homepage")
    return "/" + value


def url_filters(config: dict):
    prefix = base_url(config.get("baseurl"))
    origin = str(config.get("url") or "").rstrip("/")

    def relative_url(value):
        value = str(value or "")
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc:
            return value
        path = "/" + parsed.path.lstrip("/")
        if prefix and path != prefix and not path.startswith(prefix + "/"):
            path = prefix + path
        return urlunsplit(("", "", path, parsed.query, parsed.fragment))

    def absolute_url(value):
        value = str(value or "")
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc:
            return value
        return origin + relative_url(value)

    return relative_url, absolute_url


def load_data() -> dict:
    data = {}
    for path in sorted(walk_files(source_path("_data"))):
        if path.suffix.lower() not in (".yml", ".yaml"):
            continue
        relative = path.relative_to(ROOT / "_data").with_suffix("")
        target = data
        for part in relative.parts[:-1]:
            target = target.setdefault(part, {})
        target[relative.name] = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    return data


def excluded(relative: str, config: dict) -> bool:
    for pattern in config.get("exclude", []):
        pattern = str(pattern).strip("/")
        if relative == pattern or relative.startswith(pattern + "/") or fnmatch.fnmatchcase(relative, pattern):
            return True
    return False


def page_defaults(config: dict, relative: str) -> dict:
    defaults = {}
    for item in config.get("defaults", []):
        scope = item.get("scope", {})
        prefix = str(scope.get("path") or "").strip("/")
        if scope.get("type") not in (None, "", "pages"):
            continue
        if not prefix or relative == prefix or relative.startswith(prefix + "/") or fnmatch.fnmatchcase(relative, prefix):
            defaults.update(item.get("values", {}))
    return defaults


def url_output_path(value: str) -> str:
    """Map a site-relative permalink to a file, never to a baseurl directory."""
    value = str(value or "/")
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or "\\" in value:
        raise ValueError("Invalid page permalink/redirect: " + value)
    parts = parsed.path.strip("/").split("/") if parsed.path.strip("/") else []
    if any(part in ("", ".", "..") or ":" in part or part.startswith(".") for part in parts):
        raise ValueError("Unsafe page permalink/redirect: " + value)
    if not parts or parsed.path.endswith("/"):
        parts.append("index.html")
    return "/".join(parts)


def reload_script(revision: Optional[str], prefix: str) -> str:
    return """<script data-local-preview>
(function () {
  const revision = %s;
  const baseurl = %s;
  async function check() {
    try {
      const response = await fetch(%s, {cache: 'no-store'});
      if (!response.ok) {
        if (revision !== null) { window.location.reload(); return; }
      } else {
        const state = await response.json();
        if (revision === null || state.revision !== revision) {
          if (state.baseurl !== baseurl) {
            window.location.replace(state.home_url + window.location.hash);
          } else {
            window.location.reload();
          }
          return;
        }
      }
    } catch (error) { /* A stopped preview server should not disturb the page. */ }
    window.setTimeout(check, 1000);
  }
  window.setTimeout(check, 1000);
})();
</script>""" % (json.dumps(revision), json.dumps(prefix), json.dumps(REVISION_ENDPOINT))


@dataclass
class RenderedSite:
    files: Dict[str, bytes]
    html_paths: Set[str]
    baseurl: str
    home_url: str


def render_site(config: dict, revision: str, preview: bool = False) -> RenderedSite:
    prefix = base_url(config.get("baseurl"))
    relative_url, absolute_url = url_filters(config)
    markdown = mistune.create_markdown(escape=False, plugins=["table", "strikethrough", "task_lists", "footnotes"])
    env = liquid.Environment(loader=JekyllIncludeLoader(source_path("_includes"),
                                                       encoding="utf-8-sig", reject_symlinks=True),
                             autoescape=False, strict_filters=True)
    env.add_filter("relative_url", relative_url)
    env.add_filter("absolute_url", absolute_url)
    env.add_filter("markdownify", lambda value: markdown(str(value or "")))
    site = dict(config)
    site.update(baseurl=prefix, data=load_data(), posts=[])
    pages = []
    extensions = {"." + ext.strip() for ext in str(config.get("markdown_ext", "md,markdown")).split(",")}
    for path in sorted(walk_files(source_path("_pages"))):
        relative = path.relative_to(ROOT).as_posix()
        if excluded(relative, config) or path.suffix.lower() not in extensions | {".html"}:
            continue
        matter, body = split_front_matter(path.read_text(encoding="utf-8-sig"), relative)
        page = page_defaults(config, relative)
        page.update(matter)
        fallback = "/" + path.relative_to(ROOT / "_pages").with_suffix(".html").as_posix()
        page["url"] = str(page.get("permalink") or fallback)
        page["path"] = relative
        page.setdefault("title", path.stem)
        pages.append((path, page, body))
    if not pages:
        raise ValueError("No Markdown/HTML pages found in _pages")
    site["pages"] = [page for _, page, _ in pages]
    outputs = {}
    html_paths = set()
    home_url = relative_url("/")
    redirects = []
    for path, page, body in pages:
        rendered = env.from_string(preprocess_includes(body), name=page["path"]).render(site=site, page=page)
        content = markdown(rendered) if path.suffix.lower() in extensions else rendered
        page["content"] = content
        layout = page.get("layout")
        seen = set()
        while layout and layout != "none":
            layout = str(layout)
            if layout in seen or len(seen) >= 12:
                raise ValueError("Circular/excessive layout chain: " + layout)
            seen.add(layout)
            layout_path = source_path("_layouts/" + layout + ".html")
            if not within(layout_path.resolve(), source_path("_layouts").resolve()):
                raise ValueError("Layout path escapes _layouts: " + layout)
            matter, source = split_front_matter(layout_path.read_text(encoding="utf-8-sig"), str(layout_path))
            content = env.from_string(preprocess_includes(source), name="_layouts/" + layout + ".html").render(
                site=site, page=page, content=content)
            layout = matter.get("layout")
        if "{{" in content or "{%" in content:
            raise ValueError("Unrendered Liquid remains in " + page["path"])
        if preview:
            script = reload_script(revision, prefix)
            if re.search(r"</body\s*>", content, re.I):
                content = re.sub(r"</body\s*>", lambda match: script + "\n" + match.group(0), content, count=1, flags=re.I)
            else:
                content += "\n" + script
        destination = url_output_path(page["url"])
        if destination in outputs:
            raise ValueError("Duplicate page permalink: " + page["url"])
        outputs[destination] = content.encode("utf-8")
        html_paths.add(destination)
        if path.name == "about.md" or page["url"] == "/":
            home_url = relative_url(page["url"])
        aliases = page.get("redirect_from", []) or []
        if isinstance(aliases, str):
            aliases = [aliases]
        redirects.extend((str(alias), page["url"]) for alias in aliases)

    for alias, target in redirects:
        destination = url_output_path(alias)
        if destination == url_output_path(target):
            continue
        if destination in outputs:
            raise ValueError("Redirect collides with a page: " + alias)
        local_target = relative_url(target)
        escaped_target = html.escape(local_target, quote=True)
        redirect = (
            '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Redirecting</title><link rel="canonical" href="' + html.escape(absolute_url(target), quote=True) + '">'
            '<meta http-equiv="refresh" content="0;url=' + escaped_target + '"></head>'
            '<body><p><a href="' + escaped_target + '">Continue to the homepage</a></p>'
            '<script>window.location.replace(' + json.dumps(local_target) + ' + window.location.hash);</script>'
            '</body></html>\n'
        )
        outputs[destination] = redirect.encode("utf-8")
        html_paths.add(destination)

    # Publish only public asset directories. Never copy source pages, tools,
    # dependency files, Git metadata, or screenshots into the served directory.
    for directory in STATIC_DIRS:
        for path in sorted(walk_files(source_path(directory))):
            relative = path.relative_to(ROOT).as_posix()
            if excluded(relative, config) or path.suffix.lower() in extensions | {".scss", ".sass", ".py", ".rb", ".yml", ".yaml", ".liquid"}:
                continue
            if relative in outputs:
                raise ValueError("Static asset collides with generated output: " + relative)
            outputs[relative] = path.read_bytes()

    _, scss = split_front_matter(source_path("assets/css/main.scss").read_text(encoding="utf-8-sig"), "assets/css/main.scss")
    sass_options = config.get("sass", {}) or {}
    sass_directory = source_path(str(sass_options.get("sass_dir") or "_sass"))
    css = sass.compile(string=scss, include_paths=[str(sass_directory)],
                       output_style=str(sass_options.get("style") or "compressed"))
    outputs["assets/css/main.css"] = css.encode("utf-8")
    return RenderedSite(outputs, html_paths, prefix, home_url)


def check_site_root() -> None:
    if SITE.is_symlink() or SITE.resolve() != SITE or not within(SITE.resolve(), ROOT):
        raise ValueError("_site must be a real directory inside the homepage")
    if SITE.exists() and not SITE.is_dir():
        raise ValueError("_site is not a directory")


def output_path(relative: str) -> Path:
    check_site_root()
    destination = SITE.joinpath(*PurePosixPath(relative).parts)
    if not within(destination.resolve(), SITE) or destination.is_symlink():
        raise ValueError("Output path escapes _site: " + relative)
    return destination


def write_site(rendered: RenderedSite) -> None:
    check_site_root()
    # Validate every existing output path before writing or removing anything.
    existing = list(walk_files(SITE, skip_hidden=False))
    SITE.mkdir(exist_ok=True)
    for relative, content in sorted(rendered.files.items()):
        destination = output_path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_path(relative + ".preview-tmp")
        with temporary.open("wb") as stream:
            stream.write(content)
        os.replace(str(temporary), str(destination))
    for path in existing:
        relative = path.relative_to(SITE).as_posix()
        if relative not in rendered.files:
            output_path(relative).unlink()
    # Removing empty generated directories is confined to the verified _site.
    for current, directories, _ in os.walk(str(SITE), topdown=False, followlinks=False):
        for name in directories:
            directory = output_path((Path(current) / name).relative_to(SITE).as_posix())
            if not any(directory.iterdir()):
                directory.rmdir()


def source_revision() -> str:
    paths = [source_path("_config.yml")]
    for directory in SOURCE_DIRS:
        paths.extend(walk_files(source_path(directory)))
    digest = hashlib.sha256()
    for path in sorted(paths):
        info = path.stat()
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        digest.update((":{}:{}\n".format(info.st_mtime_ns, info.st_size)).encode("ascii"))
    return digest.hexdigest()[:20]


class BuildState:
    def __init__(self, preview: bool):
        self.preview = preview
        self.revision = None
        self.attempted_revision = None
        self.last_attempt = 0.0
        self.error = None
        self.baseurl = ""
        self.home_url = "/"
        self.html_paths = set()
        self.lock = threading.Lock()

    def ensure_current(self, force: bool = False) -> bool:
        with self.lock:
            try:
                revision = source_revision()
                if not force and revision == self.attempted_revision:
                    if self.error is None:
                        return True
                    if time.monotonic() - self.last_attempt < 1.0:
                        return False
                self.attempted_revision = revision
                self.last_attempt = time.monotonic()
                for _ in range(3):
                    rendered = render_site(read_yaml(source_path("_config.yml")), revision, self.preview)
                    latest = source_revision()
                    if latest == revision:
                        break
                    revision = latest
                else:
                    raise ValueError("Source files are changing during the build; save them and retry")
                write_site(rendered)
                self.revision = revision
                self.attempted_revision = revision
                self.baseurl = rendered.baseurl
                self.home_url = rendered.home_url
                self.html_paths = rendered.html_paths
                self.error = None
                print("[preview] Built {} files in _site (revision {}).".format(len(rendered.files), revision), flush=True)
                return True
            except Exception as exc:
                message = "{}: {}".format(type(exc).__name__, exc)
                if message != self.error:
                    print("[preview] Build failed: " + message, file=sys.stderr, flush=True)
                self.error = message
                return False


def request_file(request_path: str, prefix: str) -> Tuple[Optional[Path], Optional[str]]:
    """Resolve an HTTP URL only within _site; return a redirect when needed."""
    path = unquote(urlsplit(request_path).path, errors="strict")
    if "\\" in path or "\x00" in path:
        raise ValueError("Invalid request path")
    parts = path.split("/")
    if any(part.startswith(".") or ":" in part for part in parts):
        raise ValueError("Invalid request path")
    if prefix:
        if path == "/" or path == prefix:
            return None, prefix + "/"
        if not path.startswith(prefix + "/"):
            return None, None
        path = path[len(prefix):]
    destination = output_path(path.lstrip("/") or "index.html")
    if destination.is_dir():
        if not path.endswith("/"):
            return None, prefix + path + "/"
        destination = output_path((destination / "index.html").relative_to(SITE).as_posix())
    return destination, None


def handler_for(state: BuildState):
    class PreviewHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.respond(head=False)

        def do_HEAD(self):
            self.respond(head=True)

        def send_bytes(self, status: int, content: bytes, content_type: str, head: bool = False, location: Optional[str] = None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.send_header("X-Content-Type-Options", "nosniff")
            if location is not None:
                self.send_header("Location", location)
            self.end_headers()
            if not head:
                self.wfile.write(content)

        def respond(self, head: bool):
            ready = state.ensure_current()
            if urlsplit(self.path).path == REVISION_ENDPOINT:
                payload = {"revision": state.revision, "baseurl": state.baseurl,
                           "home_url": state.home_url, "error": state.error}
                self.send_bytes(200 if ready else 500, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8", head)
                return
            if not ready:
                content = ('<!doctype html><meta charset="utf-8"><title>Preview build error</title>'
                           '<style>body{font:16px/1.6 system-ui;max-width:900px;margin:40px auto;padding:20px}'
                           'pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>'
                           '<h1>Preview build failed</h1><p>Fix the source and save. The preview will retry automatically.</p>'
                           '<pre>' + html.escape(state.error or "Unknown build error") + '</pre>'
                           + reload_script(None, state.baseurl))
                self.send_bytes(500, content.encode("utf-8"), "text/html; charset=utf-8", head)
                return
            try:
                destination, redirect = request_file(self.path, state.baseurl)
                if redirect is not None:
                    self.send_bytes(302, b"", "text/plain; charset=utf-8", head, location=redirect)
                    return
                if destination is None or not destination.is_file():
                    self.send_bytes(404, b"Not found\n", "text/plain; charset=utf-8", head)
                    return
                relative = destination.relative_to(SITE).as_posix()
                types = {".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8"}
                content_type = ("text/html; charset=utf-8" if relative in state.html_paths else
                                types.get(destination.suffix.lower()) or mimetypes.guess_type(str(destination))[0] or "application/octet-stream")
                self.send_bytes(200, destination.read_bytes(), content_type, head)
            except (ValueError, UnicodeError):
                self.send_bytes(400, b"Invalid request path\n", "text/plain; charset=utf-8", head)
            except OSError as exc:
                self.send_bytes(500, str(exc).encode("utf-8"), "text/plain; charset=utf-8", head)

        def log_message(self, format, *args):
            if urlsplit(self.path).path != REVISION_ENDPOINT:
                super().log_message(format, *args)

    return PreviewHandler


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--build", action="store_true", help="Build _site once without the local reload script")
    parser.add_argument("--port", type=int, default=8765, help="Local preview port (default: 8765)")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    state = BuildState(preview=not args.build)
    if not state.ensure_current(force=True):
        return 1
    if args.build:
        return 0
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(state))
    except OSError as exc:
        print("[preview] Cannot start server: " + str(exc), file=sys.stderr)
        return 1
    print("[preview] Open http://127.0.0.1:{}{}".format(args.port, state.home_url), flush=True)
    print("[preview] Save source files to rebuild and refresh. Ctrl+C stops the server.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[preview] Stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
