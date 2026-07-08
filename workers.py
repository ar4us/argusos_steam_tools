import os
import zipfile
import tempfile
import uuid
from pathlib import Path
import requests
from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot

import utils


class CancellableDlSig(QObject):
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    cancelled = pyqtSignal()


class CancellableDlWorker(QRunnable):
    def __init__(self, url, dest):
        super().__init__()
        self.url = url
        self.dest = dest
        self.sig = CancellableDlSig()
        self._is_cancelled = False
        self._current_request = None

    def cancel(self):
        self._is_cancelled = True
        if self._current_request:
            self._current_request.close()

    @pyqtSlot()
    def run(self):
        if self._is_cancelled:
            self.sig.cancelled.emit()
            return
        try:
            name = self.url.split("/")[-1]
            is_zip = name.lower().endswith(".zip")
            if is_zip:
                temp_zip = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex + ".zip")
                dest_folder = self.dest
                final_path = temp_zip
            else:
                temp_zip = self.dest
                dest_folder = None
                final_path = self.dest

            Path(final_path).parent.mkdir(parents=True, exist_ok=True)
            self._current_request = requests.get(
                self.url, stream=True, timeout=15, verify=False
            )
            total = int(self._current_request.headers.get("content-length", 0))
            done = 0
            with open(final_path, "wb") as f:
                for chunk in self._current_request.iter_content(8192):
                    if self._is_cancelled:
                        self._current_request.close()
                        self.sig.cancelled.emit()
                        return
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        self.sig.progress.emit(int(done / total * 100))
            self._current_request.close()
            self._current_request = None

            if is_zip:
                with zipfile.ZipFile(temp_zip, "r") as z:
                    files = z.namelist()
                    ztotal = len(files)
                    for i, fn in enumerate(files):
                        z.extract(fn, dest_folder)
                        if ztotal:
                            self.sig.progress.emit(int((i + 1) / ztotal * 100))
                os.unlink(temp_zip)
                self.sig.finished.emit(True, dest_folder)
            else:
                self.sig.finished.emit(True, self.dest)
        except Exception as e:
            self.sig.finished.emit(False, str(e))


class DownloadSig(QObject):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    cancelled = pyqtSignal()


class DownloadWorker(QRunnable):
    def __init__(self, url, dest_path, extract_to=""):
        super().__init__()
        self.url = url
        self.dest_path = Path(dest_path)
        self.extract_to = extract_to
        self.sig = DownloadSig()

    @pyqtSlot()
    def run(self):
        try:
            self.sig.status.emit("Downloading...")
            temp_zip = os.path.join(
                tempfile.gettempdir(), uuid.uuid4().hex + ".zip"
            )
            utils.download_file(
                self.url, temp_zip,
                progress_callback=lambda p: self.sig.progress.emit(p),
            )
            self.sig.status.emit("Extracting...")
            utils.extract_zip(
                temp_zip, str(self.extract_to if self.extract_to else self.dest_path),
                progress_callback=lambda p: self.sig.progress.emit(p),
            )
            os.unlink(temp_zip)
            self.sig.finished.emit(
                True, str(self.dest_path if self.extract_to else self.dest_path)
            )
        except Exception as e:
            self.sig.finished.emit(False, str(e))


class ManifestWorker(QRunnable):
    def __init__(self, appid, lua_dir):
        super().__init__()
        self.appid = appid
        self.lua_dir = Path(lua_dir)
        self.sig = DownloadSig()

    @pyqtSlot()
    def run(self):
        try:
            self.sig.status.emit("Downloading...")
            url = f"https://polarservices.org/manifests/{self.appid}"
            r = requests.get(url, timeout=15, verify=False)
            if r.status_code != 200:
                self.sig.finished.emit(False, f"HTTP {r.status_code}")
                return

            content = r.content
            if content.startswith(b"PK"):
                self.sig.progress.emit(50)
                temp_zip = os.path.join(
                    tempfile.gettempdir(), uuid.uuid4().hex + ".zip"
                )
                with open(temp_zip, "wb") as f:
                    f.write(content)
                self.sig.status.emit("Extracting...")
                utils.extract_zip(
                    temp_zip, str(self.lua_dir),
                    progress_callback=lambda p: self.sig.progress.emit(50 + p // 2),
                )
                os.unlink(temp_zip)
                for f in self.lua_dir.iterdir():
                    if f.suffix == ".lua":
                        utils.cleanup_manifest(f.parent)
                        self.sig.finished.emit(True, str(f))
                        return
                self.sig.finished.emit(False, "No .lua file found in manifest")
            else:
                lua_file = self.lua_dir / f"{self.appid}.lua"
                with open(lua_file, "wb") as f:
                    f.write(content)
                utils.cleanup_manifest(self.lua_dir)
                self.sig.finished.emit(True, str(lua_file))
        except Exception as e:
            self.sig.finished.emit(False, str(e))


class ImgSig(QObject):
    loaded = pyqtSignal(str, object)


class ImgWorker(QRunnable):
    _cache = {}

    def __init__(self, key):
        super().__init__()
        self.key = key
        self.sig = ImgSig()

    @pyqtSlot()
    def run(self):
        from PyQt5.QtGui import QPixmap
        if self.key in self._cache:
            self.sig.loaded.emit(self.key, self._cache[self.key])
            return

        # If key is appid, construct CDN URL directly to bypass WAF!
        if not self.key.startswith("http"):
            # Try capsule_184x69.jpg first
            url = f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{self.key}/capsule_184x69.jpg"
            try:
                r = requests.get(url, timeout=10, verify=False)
                if r.status_code == 200:
                    pix = QPixmap()
                    pix.loadFromData(r.content)
                    self._cache[self.key] = pix
                    self.sig.loaded.emit(self.key, pix)
                    return
            except:
                pass
            
            # Fall back to header.jpg
            url = f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{self.key}/header.jpg"
            try:
                r = requests.get(url, timeout=10, verify=False)
                if r.status_code == 200:
                    pix = QPixmap()
                    pix.loadFromData(r.content)
                    self._cache[self.key] = pix
                    self.sig.loaded.emit(self.key, pix)
                    return
            except:
                pass
                
            self.sig.loaded.emit(self.key, QPixmap())
            return
        else:
            # Full HTTP URL
            url = self.key
            try:
                r = requests.get(url, timeout=15, verify=False)
                pix = QPixmap()
                pix.loadFromData(r.content)
                self._cache[self.key] = pix
                self.sig.loaded.emit(self.key, pix)
            except:
                self.sig.loaded.emit(self.key, QPixmap())


class LibraryGameSig(QObject):
    loaded = pyqtSignal(str, object, str)


class LibraryGameWorker(QRunnable):
    _cache = {}

    def __init__(self, appid):
        super().__init__()
        self.appid = appid
        self.sig = LibraryGameSig()

    @pyqtSlot()
    def run(self):
        from PyQt5.QtGui import QPixmap
        try:
            if self.appid in self._cache:
                pix, name = self._cache[self.appid]
                self.sig.loaded.emit(self.appid, pix, name)
                return

            # 1. Resolve game name using SteamSpy
            name = f"Game {self.appid}"
            try:
                spy_url = f"https://steamspy.com/api.php?request=appdetails&appid={self.appid}"
                resp = requests.get(spy_url, timeout=10, verify=False)
                if resp.status_code == 200:
                    spy_data = resp.json()
                    spy_name = spy_data.get("name")
                    if spy_name and spy_name != "null":
                        name = spy_name
            except Exception as e:
                print(f"SteamSpy failed for {self.appid}: {e}")
                # Fallback to local appdetails if it works
                try:
                    steam_url = "https://store.steampowered.com/api/appdetails"
                    resp = requests.get(
                        steam_url,
                        params={"appids": self.appid, "filters": "basic"},
                        timeout=5,
                        verify=False
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        appdata = data.get(str(self.appid), {}).get("data", {})
                        steam_name = appdata.get("name")
                        if steam_name:
                            name = steam_name
                except:
                    pass

            # 2. Get game image directly from Steam CDN
            pix = QPixmap()
            # Try capsule_184x69.jpg
            img_url = f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{self.appid}/capsule_184x69.jpg"
            try:
                r = requests.get(img_url, timeout=10, verify=False)
                if r.status_code == 200:
                    pix.loadFromData(r.content)
                else:
                    # Fallback to header.jpg
                    header_url = f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{self.appid}/header.jpg"
                    r = requests.get(header_url, timeout=10, verify=False)
                    if r.status_code == 200:
                        pix.loadFromData(r.content)
            except:
                pass

            self._cache[self.appid] = (pix, name)
            self.sig.loaded.emit(self.appid, pix, name)
        except Exception as e:
            print(f"LibraryGameWorker error for {self.appid}: {e}")
            self.sig.loaded.emit(self.appid, QPixmap(), f"Game {self.appid}")


class DeleteGameSig(QObject):
    finished = pyqtSignal(str, bool)


class DeleteGameWorker(QRunnable):
    def __init__(self, lua_file):
        super().__init__()
        self.lua_file = lua_file
        self.sig = DeleteGameSig()

    @pyqtSlot()
    def run(self):
        try:
            path = Path(self.lua_file)
            if path.exists():
                path.unlink()
                utils.cleanup_manifest(path.parent)
            self.sig.finished.emit(path.stem, True)
        except Exception as e:
            self.sig.finished.emit(str(e), False)


class DllDownloadSig(QObject):
    finished = pyqtSignal()


class DllDownloadWorker(QRunnable):
    def __init__(self):
        super().__init__()
        self.sig = DllDownloadSig()

    @pyqtSlot()
    def run(self):
        try:
            steam_path = utils.get_steam_path()
            steam_dir = Path(steam_path) if steam_path else Path.cwd()
            files = [
                ("OpenSteamTool.dll",
                 "https://raw.githubusercontent.com/857seif/tecno-tool/main/input/OpenSteamTool.dll"),
                ("dwmapi.dll",
                 "https://raw.githubusercontent.com/857seif/tecno-tool/main/input/dwmapi.dll"),
                ("xinput1_4.dll",
                 "https://raw.githubusercontent.com/857seif/tecno-tool/main/input/xinput1_4.dll"),
            ]
            for filename, url in files:
                dest = steam_dir / filename
                if not dest.exists():
                    r = requests.get(url, timeout=15, verify=False)
                    if r.status_code == 200:
                        with open(dest, "wb") as f:
                            f.write(r.content)
        except:
            pass
        finally:
            self.sig.finished.emit()


import requests

# ─────────────────────────────────────────────────────────────────────────────
# Online Fix — Search, AppID resolution, and Icon workers
# ─────────────────────────────────────────────────────────────────────────────

class OFSearchSig(QObject):
    finished = pyqtSignal(list)
    error    = pyqtSignal(str)

class OFSearchWorker(QRunnable):
    """Searches online-fix.me and returns a list of {title, url, stem} dicts."""
    def __init__(self, query):
        super().__init__()
        self.query = query
        self.sig   = OFSearchSig()

    @pyqtSlot()
    def run(self):
        import re
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            self.sig.error.emit("BeautifulSoup4 not installed. Run: pip install beautifulsoup4")
            return

        url  = "https://online-fix.me/index.php?do=search"
        hdrs = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Origin":  "https://online-fix.me",
            "Referer": "https://online-fix.me/",
        }
        data = {
            "do": "search", "subaction": "search",
            "search_start": 1, "full_search": 0, "result_from": 1,
            "story": self.query,
        }
        try:
            r = requests.post(url, data=data, headers=hdrs, timeout=15, verify=False)
            if r.status_code != 200:
                self.sig.error.emit(f"Server returned {r.status_code}")
                return
            soup    = BeautifulSoup(r.text, "html.parser")
            matches = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/games/" in href and href.endswith(".html"):
                    if href.startswith("/"):
                        href = "https://online-fix.me" + href
                    stem       = href.split("/")[-1].replace(".html", "")
                    clean_name = re.sub(r"^\d+-", "", stem).replace("-po-seti", "")
                    title      = clean_name.replace("-", " ").title()
                    if not any(m["url"] == href for m in matches):
                        matches.append({"title": title, "url": href, "stem": stem})
            self.sig.finished.emit(matches)
        except Exception as e:
            self.sig.error.emit(str(e))


class OFAppIdSig(QObject):
    done = pyqtSignal(str, str)   # stem, appid

class OFAppIdWorker(QRunnable):
    """Resolves a game title to its Steam AppID via the Steam store search API."""
    def __init__(self, stem, title):
        super().__init__()
        self.stem  = stem
        self.title = title
        self.sig   = OFAppIdSig()

    @pyqtSlot()
    def run(self):
        import urllib.parse
        try:
            url  = ("https://store.steampowered.com/api/storesearch/"
                    f"?term={urllib.parse.quote(self.title)}&l=en&cc=US")
            hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            r    = requests.get(url, headers=hdrs, timeout=10, verify=False)
            if r.status_code == 200:
                items = r.json().get("items", [])
                if items:
                    self.sig.done.emit(self.stem, str(items[0]["id"]))
        except Exception:
            pass


class OFIconSig(QObject):
    done = pyqtSignal(str, object)   # stem, QPixmap

class OFIconWorker(QRunnable):
    """
    Fetches a Steam header.jpg for the given appid.
    Strategy 1 — plain CDN URL (works for ~90% of games).
    Strategy 2 — appdetails API fallback (newer games with content-hashed CDN paths).
    """
    def __init__(self, stem, appid):
        super().__init__()
        self.stem  = stem
        self.appid = appid
        self.sig   = OFIconSig()

    @pyqtSlot()
    def run(self):
        from PyQt5.QtGui import QPixmap
        from PyQt5.QtCore import Qt
        hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        img_data = None

        # Strategy 1 — plain CDN
        for cdn in (
            f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{self.appid}/header.jpg",
            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{self.appid}/header.jpg",
        ):
            try:
                r = requests.get(cdn, headers=hdrs, timeout=8, verify=False)
                if r.status_code == 200 and len(r.content) > 500:
                    img_data = r.content
                    break
            except Exception:
                continue

        # Strategy 2 — appdetails fallback
        if not img_data:
            try:
                api = f"https://store.steampowered.com/api/appdetails?appids={self.appid}"
                r   = requests.get(api, headers=hdrs, timeout=12, verify=False)
                if r.status_code == 200:
                    real_url = (r.json()
                                .get(str(self.appid), {})
                                .get("data", {})
                                .get("header_image", ""))
                    if real_url:
                        r2 = requests.get(real_url, headers=hdrs, timeout=10, verify=False)
                        if r2.status_code == 200 and len(r2.content) > 500:
                            img_data = r2.content
            except Exception:
                pass

        if img_data:
            try:
                pix = QPixmap()
                pix.loadFromData(img_data)
                if not pix.isNull():
                    pix = pix.scaled(80, 44, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                    if pix.width() > 80 or pix.height() > 44:
                        x = max(0, (pix.width() - 80) // 2)
                        y = max(0, (pix.height() - 44) // 2)
                        pix = pix.copy(x, y, 80, 44)
                    self.sig.done.emit(self.stem, pix)
            except Exception:
                pass


class OFDownloadSig(QObject):
    progress = pyqtSignal(int)
    status   = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

class OFDownloadWorker(QRunnable):
    """
    Fetches the rehosted ZIP URL from opela.team then downloads + extracts it
    into the chosen game folder.
    """
    def __init__(self, game_url, stem, extract_folder):
        super().__init__()
        self.game_url       = game_url
        self.stem           = stem
        self.extract_folder = Path(extract_folder)
        self.sig            = OFDownloadSig()

    @pyqtSlot()
    def run(self):
        hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        # 1. Resolve download link via Opela
        self.sig.status.emit("Fetching download link…")
        dl_url = None
        try:
            params = {
                "path": "onlinefix-download",
                "url":  self.game_url,
                "gamename": self.stem,
            }
            r = requests.get("https://www.opela.team/api/downloads",
                             params=params, headers=hdrs, timeout=45, verify=False)
            if r.status_code == 200:
                data = r.json()
                if data.get("success"):
                    dl_url = data.get("data", {}).get("rehosted")
            if not dl_url:
                self.sig.finished.emit(False, "Could not resolve download URL from Opela API.")
                return
        except Exception as e:
            self.sig.finished.emit(False, f"Opela API error: {e}")
            return

        # 2. Download ZIP
        self.sig.status.emit("Downloading fix files…")
        tmp = os.path.join(tempfile.gettempdir(), uuid.uuid4().hex + ".zip")
        try:
            r     = requests.get(dl_url, stream=True, verify=False, timeout=60, headers=hdrs)
            total = int(r.headers.get("content-length", 0))
            done  = 0
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        self.sig.progress.emit(int(done / total * 100))
        except Exception as e:
            if os.path.exists(tmp):
                os.unlink(tmp)
            self.sig.finished.emit(False, f"Download error: {e}")
            return

        # 3. Extract
        self.sig.status.emit("Extracting files into game folder…")
        try:
            self.extract_folder.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(tmp, "r") as z:
                files = z.namelist()
                for i, fn in enumerate(files):
                    z.extract(fn, self.extract_folder)
                    if files:
                        self.sig.progress.emit(int((i + 1) / len(files) * 100))
            os.unlink(tmp)
            self.sig.finished.emit(True, str(self.extract_folder))
        except Exception as e:
            if os.path.exists(tmp):
                os.unlink(tmp)
            self.sig.finished.emit(False, f"Extraction error: {e}")
