import winreg
import tempfile
import uuid
import os
from pathlib import Path
import requests


def get_steam_path():
    for subkey in [
        r"SOFTWARE\WOW6432Node\Valve\Steam",
        r"SOFTWARE\Valve\Steam",
    ]:
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey)
            path, _ = winreg.QueryValueEx(key, "InstallPath")
            key.Close()
            if path:
                return path
        except:
            pass
    return None


def download_file(url, dest_path, progress_callback=None):
    Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, stream=True, verify=False, timeout=15)
    total = int(r.headers.get("content-length", 0))
    done = 0
    with open(dest_path, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
            done += len(chunk)
            if progress_callback and total:
                progress_callback(int(done / total * 100))
    return dest_path


def extract_zip(zip_path, extract_to, progress_callback=None):
    import zipfile
    with zipfile.ZipFile(zip_path, "r") as z:
        files = z.namelist()
        total = len(files)
        for i, fn in enumerate(files):
            z.extract(fn, extract_to)
            if progress_callback and total:
                progress_callback(int((i + 1) / total * 100))
    return extract_to


def cleanup_manifest(folder):
    folder_path = Path(folder)
    if folder_path.exists():
        for file_path in folder_path.rglob("*.manifest"):
            file_path.unlink()


def prepare_lua_folder(steam_path):
    base = Path(steam_path)
    config = base / "config"
    if config.exists() and not config.is_dir():
        import shutil
        shutil.move(str(config), str(config) + "_bak")
    lua_dir = config / "lua"
    lua_dir.mkdir(parents=True, exist_ok=True)
    return str(lua_dir)


def fetch_app_image_url(appid):
    base = "https://cdn.cloudflare.steamstatic.com/steamcommunity/public/images/apps"
    try:
        r = requests.get(
            "https://store.steampowered.com/api/appdetails",
            params={"appids": appid, "filters": "basic"},
            timeout=15,
            verify=False,
        )
        data = r.json()
        appdata = data.get(str(appid), {}).get("data", {})
        for key in ("header_image", "capsule"):
            val = appdata.get(key)
            if val and isinstance(val, str):
                return val
        icon_hash = appdata.get("icon")
        if icon_hash:
            return f"{base}/{appid}/{icon_hash}.jpg"
    except:
        pass
    return None
