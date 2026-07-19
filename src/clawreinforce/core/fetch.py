from __future__ import annotations

import io
import json
import shutil
import tempfile
import urllib.parse
import urllib.request
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from clawreinforce.errors import ClawError


def _download(url: str) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "clawreinforce/0.1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read(), response.headers.get("Content-Type", "")


def _extract_zip(data: bytes, target: Path) -> None:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for info in archive.infolist():
            path = (target / info.filename).resolve()
            if target.resolve() not in path.parents and path != target.resolve():
                raise ClawError("fetch.unsafe_archive", "security", "archive contains an unsafe path")
        archive.extractall(target)


def fetch_github_tree(source: str, destination: Path) -> None:
    parsed = urllib.parse.urlparse(source)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise ClawError("fetch.github_url", "validation", "GitHub URL must include owner/repo")
    owner, repo = parts[0], parts[1].removesuffix(".git")
    ref = "HEAD"
    wanted = ""
    if len(parts) >= 5 and parts[2] == "tree":
        ref, wanted = parts[3], "/".join(parts[4:])
    data, _ = _download(f"https://api.github.com/repos/{owner}/{repo}/zipball/{urllib.parse.quote(ref)}")
    unpack = destination.parent / "github-archive"
    unpack.mkdir()
    _extract_zip(data, unpack)
    top = next(path for path in unpack.iterdir() if path.is_dir())
    selected = top / wanted if wanted else top
    if not selected.exists():
        raise ClawError("fetch.github_path", "not_found", "path was not found in GitHub archive", path=wanted)
    shutil.copytree(selected, destination, dirs_exist_ok=True)


def clawhub_slug(source: str) -> str:
    clean = source.removeprefix("clawhub:").strip()
    parsed = urllib.parse.urlparse(clean)
    if parsed.scheme:
        if parsed.netloc.lower() not in {"clawhub.ai", "www.clawhub.ai"}:
            raise ClawError("fetch.clawhub_url", "validation", "expected a clawhub.ai URL")
        parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
        if len(parts) >= 3 and parts[-2] == "skills":
            return parts[-1]
        raise ClawError("fetch.clawhub_url", "validation", "ClawHub URL must look like /owner/skills/slug")
    return clean


def _clawhub(slug: str, target: Path) -> None:
    clean = clawhub_slug(slug)
    url = "https://clawhub.ai/api/v1/download?" + urllib.parse.urlencode({"slug": clean, "tag": "latest"})
    data, content_type = _download(url)
    if "json" in content_type or data.lstrip().startswith(b"{"):
        handoff = json.loads(data)
        archive_url = handoff.get("archiveUrl")
        if not archive_url:
            raise ClawError("fetch.clawhub_handoff", "validation", "ClawHub handoff has no archiveUrl")
        data, _ = _download(archive_url)
        unpack = target / "handoff"
        unpack.mkdir()
        _extract_zip(data, unpack)
        top = next((path for path in unpack.iterdir() if path.is_dir()), unpack)
        selected = top / str(handoff.get("path", ""))
        shutil.copytree(selected, target / "skill", dirs_exist_ok=True)
        return
    (target / "skill").mkdir()
    _extract_zip(data, target / "skill")


def _locate_skill(root: Path) -> Path:
    direct = root / "SKILL.md"
    if direct.is_file():
        return root
    matches = list(root.rglob("SKILL.md"))
    if len(matches) != 1:
        raise ClawError("fetch.skill_ambiguous", "validation", "source must contain exactly one SKILL.md", count=len(matches))
    return matches[0].parent


@contextmanager
def fetched_skill(source: str) -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="clawreinforce-fetch-") as raw:
        target = Path(raw)
        local = Path(source)
        if local.exists():
            selected = local if local.is_dir() else local.parent
            shutil.copytree(selected, target / "skill")
        elif source.startswith("https://github.com/"):
            fetch_github_tree(source, target / "skill")
        else:
            _clawhub(source, target)
        yield _locate_skill(target / "skill")
