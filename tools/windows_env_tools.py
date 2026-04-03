from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from mcp.server.fastmcp import FastMCP

try:
    import winreg
except ImportError:  # pragma: no cover - only available on Windows
    winreg = None


UNINSTALL_ROOTS = (
    (
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        winreg.HKEY_LOCAL_MACHINE,
    ),
    (
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        winreg.HKEY_LOCAL_MACHINE,
    ),
    (
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        winreg.HKEY_CURRENT_USER,
    ),
) if winreg else ()

server = FastMCP("windows_env")


@dataclass(slots=True)
class InstalledApp:
    display_name: str
    registry_path: str
    publisher: str | None = None
    display_version: str | None = None
    install_location: str | None = None
    uninstall_string: str | None = None
    display_icon: str | None = None
    install_source: str | None = None
    estimated_size_kb: int | None = None
    exe_candidates: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _safe_query_value(key: "winreg.HKEYType", value_name: str) -> str | int | None:
    try:
        value, _ = winreg.QueryValueEx(key, value_name)
        return value
    except OSError:
        return None


def _split_command_path(command: str | None) -> list[Path]:
    if not command:
        return []
    candidates: list[Path] = []
    command = command.strip()

    if command.startswith('"'):
        end = command.find('"', 1)
        if end > 1:
            candidates.append(Path(command[1:end]))
    else:
        first = command.split(" ", 1)[0]
        candidates.append(Path(first))

    return candidates


def _normalize_candidate(path: Path) -> Path:
    text = str(path).strip().strip('"')
    if text.lower().startswith("rundll32") or text.lower().startswith("msiexec"):
        return Path("")
    return Path(text)


def _collect_exe_candidates(
    *,
    display_icon: str | None,
    uninstall_string: str | None,
    install_location: str | None,
    display_name: str,
) -> list[str]:
    candidates: list[Path] = []

    if display_icon:
        icon_path = display_icon.split(",", 1)[0].strip().strip('"')
        if icon_path:
            candidates.append(Path(icon_path))

    candidates.extend(_split_command_path(uninstall_string))

    if install_location:
        install_dir = Path(str(install_location).strip().strip('"'))
        preferred_names = {
            f"{display_name}.exe",
            display_name.replace(" ", "") + ".exe",
            "QQMusic.exe",
        }
        for exe in preferred_names:
            candidates.append(install_dir / exe)
        if install_dir.exists():
            try:
                for child in install_dir.glob("*.exe"):
                    candidates.append(child)
            except OSError:
                pass

    normalized: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        candidate = _normalize_candidate(candidate)
        if not candidate:
            continue
        text = str(candidate)
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def iter_installed_apps() -> Iterable[InstalledApp]:
    if winreg is None:
        raise RuntimeError("windows_env_tools only works on Windows")

    for subkey_path, hive in UNINSTALL_ROOTS:
        try:
            root = winreg.OpenKey(hive, subkey_path)
        except OSError:
            continue

        with root:
            subkey_count, _, _ = winreg.QueryInfoKey(root)
            for index in range(subkey_count):
                try:
                    subkey_name = winreg.EnumKey(root, index)
                    app_key = winreg.OpenKey(root, subkey_name)
                except OSError:
                    continue

                with app_key:
                    display_name = _safe_query_value(app_key, "DisplayName")
                    if not isinstance(display_name, str) or not display_name.strip():
                        continue
                    publisher = _safe_query_value(app_key, "Publisher")
                    display_version = _safe_query_value(app_key, "DisplayVersion")
                    install_location = _safe_query_value(app_key, "InstallLocation")
                    uninstall_string = _safe_query_value(app_key, "UninstallString")
                    display_icon = _safe_query_value(app_key, "DisplayIcon")
                    install_source = _safe_query_value(app_key, "InstallSource")
                    estimated_size_kb = _safe_query_value(app_key, "EstimatedSize")

                    yield InstalledApp(
                        display_name=display_name.strip(),
                        registry_path=f"{subkey_path}\\{subkey_name}",
                        publisher=publisher if isinstance(publisher, str) else None,
                        display_version=display_version
                        if isinstance(display_version, str)
                        else None,
                        install_location=install_location
                        if isinstance(install_location, str)
                        else None,
                        uninstall_string=uninstall_string
                        if isinstance(uninstall_string, str)
                        else None,
                        display_icon=display_icon if isinstance(display_icon, str) else None,
                        install_source=install_source
                        if isinstance(install_source, str)
                        else None,
                        estimated_size_kb=estimated_size_kb
                        if isinstance(estimated_size_kb, int)
                        else None,
                        exe_candidates=_collect_exe_candidates(
                            display_icon=display_icon
                            if isinstance(display_icon, str)
                            else None,
                            uninstall_string=uninstall_string
                            if isinstance(uninstall_string, str)
                            else None,
                            install_location=install_location
                            if isinstance(install_location, str)
                            else None,
                            display_name=display_name.strip(),
                        ),
                    )


def list_installed_apps(limit: int | None = None) -> list[InstalledApp]:
    apps = list(iter_installed_apps())
    apps.sort(key=lambda item: item.display_name.lower())
    if limit is not None:
        return apps[:limit]
    return apps


def find_installed_apps(query: str, *, limit: int = 10) -> list[InstalledApp]:
    query_lower = query.strip().lower()
    if not query_lower:
        return []

    matches: list[InstalledApp] = []
    for app in iter_installed_apps():
        haystack = " ".join(
            part
            for part in (
                app.display_name,
                app.publisher or "",
                app.install_location or "",
                " ".join(app.exe_candidates),
            )
            if part
        ).lower()
        if query_lower in haystack:
            matches.append(app)

    matches.sort(
        key=lambda item: (
            query_lower not in item.display_name.lower(),
            item.display_name.lower(),
        )
    )
    return matches[:limit]


def resolve_executable(app: InstalledApp) -> str | None:
    for candidate in app.exe_candidates:
        path = Path(candidate)
        if path.exists() and path.suffix.lower() == ".exe":
            return str(path)
    return None


def find_app_executable(query: str) -> dict:
    matches = find_installed_apps(query)
    payload = []
    for app in matches:
        item = app.to_dict()
        item["resolved_executable"] = resolve_executable(app)
        payload.append(item)
    return {"query": query, "matches": payload}


@server.tool()
def list_installed_apps_tool(limit: int = 20) -> dict:
    apps = [app.to_dict() for app in list_installed_apps(limit=limit)]
    return {"apps": apps, "count": len(apps)}


@server.tool()
def find_installed_apps_tool(query: str, limit: int = 10) -> dict:
    matches = [app.to_dict() for app in find_installed_apps(query, limit=limit)]
    return {"query": query, "matches": matches}


@server.tool()
def find_app_executable_tool(query: str) -> dict:
    return find_app_executable(query)


def main() -> int:
    args = os.sys.argv[1:]
    if args and args[0] == "--mcp":
        server.run()
        return 0

    query = " ".join(args).strip()
    if not query:
        result = {
            "message": "usage: python tools/windows_env_tools.py <query> or python tools/windows_env_tools.py --mcp",
            "example": "python tools/windows_env_tools.py QQ音乐",
        }
    else:
        result = find_app_executable(query)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
