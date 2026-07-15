import shutil
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from .models import PackageInfo


KNOWN_PRODUCTS = {"GAP", "GBMP", "GST", "GMEP"}
COPY_CHUNK_SIZE = 1024 * 1024
REMOTE_PACKAGE_PREFIXES = ("ftp://", "http://", "https://")


def is_remote_package_source(source):
    return (source or "").strip().lower().startswith(REMOTE_PACKAGE_PREFIXES)


def normalize_package_source(source):
    raw = (source or "").strip().strip('"')
    if not raw:
        raise ValueError("包路径不能为空")
    if is_remote_package_source(raw):
        return raw

    lower = raw.lower()
    if lower.startswith("file://"):
        parsed = urllib.parse.urlparse(raw)
        local_path = urllib.parse.unquote(parsed.path or "")
        if not local_path and parsed.netloc:
            local_path = f"//{parsed.netloc}{parsed.path}"
        if local_path.startswith("/") and len(local_path) >= 3 and local_path[2] == ":":
            local_path = local_path[1:]
        path = Path(local_path)
    else:
        path = Path(raw).expanduser()

    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def validate_local_package_archive(source):
    normalized = normalize_package_source(source)
    if is_remote_package_source(normalized):
        return normalized
    path = Path(normalized)
    if not path.exists():
        raise FileNotFoundError(f"包文件不存在：{path}")
    if not path.is_file():
        raise ValueError(f"包地址必须是压缩包文件：{path}")
    if path.suffix.lower() != ".zip":
        raise ValueError(f"包文件必须是 .zip 压缩包：{path}")
    return normalized


def check_cancelled(task_bus):
    if task_bus:
        task_bus.check_cancelled()


def normalize_member_name(name):
    return name.replace("\\", "/").strip("/")


def zip_single_root_prefix(members):
    roots = set()
    file_members = []
    for member in members:
        normalized = normalize_member_name(member.filename)
        if not normalized or member.is_dir():
            continue
        file_members.append(member)
        roots.add(normalized.split("/")[0])
    if len(roots) != 1:
        return ""
    root = roots.pop()
    for member in file_members:
        normalized = normalize_member_name(member.filename)
        if "/" not in normalized:
            return ""
    return f"{root}/"


def resolve_extract_dir(extract_dir):
    path = Path(extract_dir)
    if not path.is_dir():
        return path
    children = [item for item in path.iterdir()]
    if len(children) == 1 and children[0].is_dir():
        return children[0]
    return path


def extract_zip_flat(zip_file, extract_dir, task_bus=None):
    members = [member for member in zip_file.infolist() if normalize_member_name(member.filename)]
    prefix = zip_single_root_prefix(members)
    file_members = [member for member in members if not member.is_dir()]
    total = len(file_members)
    if total == 0:
        raise ValueError("压缩包内没有可解压的文件")

    extract_root = Path(extract_dir)
    extract_root.mkdir(parents=True, exist_ok=True)
    if prefix:
        print(f"[INFO] 检测到压缩包顶层目录 {prefix.rstrip('/')}，解压时将自动去除该层级")

    for index, member in enumerate(file_members, 1):
        check_cancelled(task_bus)
        normalized = normalize_member_name(member.filename)
        relative = normalized[len(prefix):] if prefix and normalized.startswith(prefix) else normalized
        if not relative:
            continue
        target = extract_root / PurePosixPath(relative).as_posix()
        if ".." in PurePosixPath(relative).parts:
            raise ValueError(f"压缩包包含非法路径：{member.filename}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with zip_file.open(member) as src, open(target, "wb") as dst:
            shutil.copyfileobj(src, dst)
        if index == 1 or index == total or index % max(1, total // 15) == 0:
            print(f"[INFO] 解压进度：{index}/{total}")

    effective_dir = resolve_extract_dir(extract_root)
    print(f"[INFO] 解压完成：{effective_dir}")
    return effective_dir


def parse_package_source(source, index=0):
    raw = normalize_package_source(source)
    normalized = raw.replace("/", "\\")
    if is_remote_package_source(raw):
        parsed = urllib.parse.urlparse(raw)
        parts = [part for part in parsed.path.split("/") if part]
        archive_name = urllib.parse.unquote(parts[-1]) if parts else Path(parsed.path).name
    else:
        path = Path(raw)
        parts = [part for part in normalized.split("\\") if part]
        archive_name = path.name

    package_name = archive_name[:-4] if archive_name.lower().endswith(".zip") else Path(archive_name).stem
    product = ""
    date = ""
    for pos, part in enumerate(parts):
        upper = part.upper()
        if upper in KNOWN_PRODUCTS:
            product = upper
            if pos + 1 < len(parts):
                date = parts[pos + 1]
    name_parts = package_name.split("_")
    if not product and name_parts:
        product = name_parts[0].upper()
    if not date and len(name_parts) > 1:
        date = name_parts[1]

    author = name_parts[3] if len(name_parts) > 3 else ""
    sdk_commit = ""
    product_commit = ""
    if product == "GBMP":
        sdk_commit = name_parts[5] if len(name_parts) > 5 and name_parts[4].upper() == "GIT" else (name_parts[4] if len(name_parts) > 4 else "")
    else:
        sdk_commit = name_parts[4] if len(name_parts) > 4 else ""
        product_commit = name_parts[5] if len(name_parts) > 5 else ""

    return PackageInfo(
        index=index,
        source=raw,
        product=product,
        date=date,
        package_name=package_name,
        archive_name=archive_name,
        author=author,
        sdk_commit=sdk_commit,
        product_commit=product_commit,
    )


def copy_file_with_cancel(source, target, task_bus=None):
    check_cancelled(task_bus)
    total_size = source.stat().st_size
    copied = 0
    print(f"[INFO] 开始复制本地包：{source}")
    with open(source, "rb") as src, open(target, "wb") as dst:
        while True:
            check_cancelled(task_bus)
            chunk = src.read(COPY_CHUNK_SIZE)
            if not chunk:
                break
            dst.write(chunk)
            copied += len(chunk)
            if total_size:
                percent = min(100, copied * 100 // total_size)
                print(f"\r[INFO] 复制进度：{percent}% ({copied}/{total_size} 字节)", end="", flush=True)
    if total_size:
        print()
    print(f"[INFO] 复制完成：{target}")


def download_file_with_cancel(source, target, task_bus=None):
    check_cancelled(task_bus)
    print(f"[INFO] 开始下载：{source}")

    def report(block_num, block_size, total_size):
        check_cancelled(task_bus)
        if total_size > 0:
            downloaded = min(block_num * block_size, total_size)
            percent = min(100, downloaded * 100 // total_size)
            print(f"\r[INFO] 下载进度：{percent}% ({downloaded}/{total_size} 字节)", end="", flush=True)

    target.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(source, target, reporthook=report)
    print(f"\n[INFO] 下载完成：{target}")


def ensure_local_archive(package, workspace, task_bus=None):
    check_cancelled(task_bus)
    archives_dir = Path(workspace) / "archives"
    archives_dir.mkdir(parents=True, exist_ok=True)
    target = archives_dir / package.archive_name
    if target.exists():
        print(f"[INFO] 复用已下载包：{target}")
        return target

    source = normalize_package_source(package.source)
    if is_remote_package_source(source):
        download_file_with_cancel(source, target, task_bus=task_bus)
    else:
        source_path = Path(source)
        if not source_path.exists():
            raise FileNotFoundError(f"包文件不存在：{source}")
        if source_path.suffix.lower() != ".zip":
            raise ValueError(f"包文件必须是 .zip 压缩包：{source}")
        copy_file_with_cancel(source_path, target, task_bus=task_bus)
    check_cancelled(task_bus)
    return target


def ensure_extracted_package(package, workspace, task_bus=None):
    check_cancelled(task_bus)
    archive = package.local_archive or ensure_local_archive(package, workspace, task_bus=task_bus)
    extract_dir = Path(workspace) / "packages" / package.package_name
    if extract_dir.exists() and any(extract_dir.iterdir()):
        effective_dir = resolve_extract_dir(extract_dir)
        if effective_dir != extract_dir:
            print(f"[INFO] 复用已解压目录（已修正层级）：{effective_dir}")
        else:
            print(f"[INFO] 复用已解压目录：{extract_dir}")
        return effective_dir

    extract_dir.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] 开始解压：{archive} -> {extract_dir}")
    with zipfile.ZipFile(archive) as zip_file:
        return extract_zip_flat(zip_file, extract_dir, task_bus=task_bus)


def prepare_package(package, workspace, task_bus=None):
    check_cancelled(task_bus)
    print(f"[INFO] 准备包 [{package.index + 1}]：{package.package_name}")
    archive = ensure_local_archive(package, workspace, task_bus=task_bus)
    extract_dir = ensure_extracted_package(
        PackageInfo(**{**package.__dict__, "local_archive": archive}),
        workspace,
        task_bus=task_bus,
    )
    print(f"[INFO] 包准备完成：{package.package_name} -> {extract_dir}")
    return PackageInfo(**{**package.__dict__, "local_archive": archive, "extract_dir": extract_dir})
