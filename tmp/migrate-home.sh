#!/bin/bash
# 版本: 1.0.0
# 用途: 将旧电脑的 /home 迁移到新电脑
# 用法: bash migrate-home.sh /mnt/oldhome
#
# 前提条件（脚本会自动检查）:
#   1. 新 Ubuntu 已安装完毕
#   2. 旧硬盘已物理装好，并通过图形界面挂载到某个路径
#   3. 当前用户为有 sudo 权限的管理员用户

set -euo pipefail

# ── 颜色输出 ───────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

info()    { echo -e "${GREEN}[INFO]${RESET}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*"; }
section() { echo -e "\n${CYAN}${BOLD}━━━ $* ━━━${RESET}"; }

# ── 帮助信息 ───────────────────────────────────────────
usage() {
    cat << EOF
用法: $(basename "$0") <旧home挂载路径>

示例:
  # 假设你通过图形界面把旧硬盘的 /home 分区挂载到了 /mnt/oldhome
  $(basename "$0") /mnt/oldhome

  # 或者挂载到了 ~/oldhome
  $(basename "$0") ~/oldhome

前提:
  1. 新 Ubuntu 已正常安装（单系统或双系统均可）
  2. 旧硬盘已物理安装到新电脑
  3. 通过文件管理器双击挂载旧 /home 分区
  4. 传入该挂载路径（可以是 ~/mnt 或 /mnt/xxx 任意位置）
EOF
    exit 1
}

# ── 参数解析 ───────────────────────────────────────────
OLD_HOME_MOUNT="${1:-}"

if [[ -z "$OLD_HOME_MOUNT" ]]; then
    error "请传入旧 home 的挂载路径。"
    echo
    usage
fi

# 展开 ~ 和相对路径
OLD_HOME_MOUNT="$(eval echo "$OLD_HOME_MOUNT")"

if [[ ! -d "$OLD_HOME_MOUNT" ]]; then
    error "路径不存在或不是目录: $OLD_HOME_MOUNT"
    error "请先通过文件管理器双击挂载旧硬盘的 /home 分区。"
    exit 1
fi

# ── 变量 ───────────────────────────────────────────────
CURRENT_USER=$(whoami)
CURRENT_HOME=$(eval echo ~)
# 获取当前用户的真实 home 路径（处理 sudo 情况）
if [[ -n "${SUDO_USER:-}" ]]; then
    CURRENT_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
    CURRENT_USER="$SUDO_USER"
fi

OLD_USER_DIR=""           # 旧 home 下第一个用户目录（如 /mnt/oldhome/john）
OLD_ACTUAL_HOME=""        # 旧 home 实际挂载的根目录
SKIP_UID_CHECK=false

# ── 步骤 0: 确认运行方式 ──────────────────────────────────
section "步骤 0 · 权限检查"

if [[ $EUID -ne 0 ]]; then
    warn "推荐用 sudo 运行，以避免后续反复输入密码。"
    warn "当前以普通用户身份运行，部分操作可能需要手动输入密码。\n"
fi

# ── 步骤 1: 定位旧 home ──────────────────────────────────
section "步骤 1 · 定位旧 /home 分区"

info "旧 home 挂载路径: $OLD_HOME_MOUNT"
info "当前用户: $CURRENT_USER"
info "当前用户 home: $CURRENT_HOME"

# 判断传入的是旧 /home 分区的挂载点，还是旧 home 下的某个目录
# 通过检测是否有 /home/user 结构的目录来判断

# 收集所有候选用户目录（排除 .Trash 等系统目录）
mapfile -t CANDIDATES < <(
    find "$OLD_HOME_MOUNT" -maxdepth 2 -mindepth 1 -type d \
         ! -name '.*' ! -name 'lost+found' ! -path '*/\.*' \
         2>/dev/null | head -20
)

if [[ ${#CANDIDATES[@]} -eq 0 ]]; then
    # 可能是直接挂载到了 /home/john 这种，直接用 mount 路径
    if [[ -d "$OLD_HOME_MOUNT" && -n "$(ls -A "$OLD_HOME_MOUNT" 2>/dev/null)" ]]; then
        OLD_USER_DIR="$OLD_HOME_MOUNT"
        info "直接将传入路径作为用户 home 目录使用。"
    else
        error "无法在 $OLD_HOME_MOUNT 下找到有效的用户目录。"
        error "请确认旧 /home 分区已正确挂载。"
        exit 1
    fi
else
    # 检查第一个候选目录的用户名
    OLD_USER_DIR="${CANDIDATES[0]}"
    OLD_USERNAME=$(basename "$OLD_USER_DIR")
    info "找到旧用户目录: $OLD_USER_DIR"
    info "旧用户名: $OLD_USERNAME"
fi

# ── 步骤 2: UID 检查 ────────────────────────────────────
section "步骤 2 · UID 对比"

# 新系统当前用户的 UID
NEW_UID=$(id -u "$CURRENT_USER")
NEW_GID=$(id -g "$CURRENT_USER")
info "新系统 UID: $NEW_UID  GID: $NEW_GID"

# 旧系统的 UID
if [[ -n "${OLD_USERNAME:-}" ]]; then
    if id "$OLD_USERNAME" &>/dev/null; then
        OLD_UID=$(id -u "$OLD_USERNAME")
        OLD_GID=$(id -g "$OLD_USERNAME")
        info "旧系统 UID: $OLD_UID  GID: $OLD_GID"
    else
        # 用户名不同，从 passwd 文件里找
        OLD_UID=$(sudo awk -v home="$OLD_USER_DIR" '
            BEGIN { found=0 }
            $6 == home { print $3; found=1; exit }
            END { if (!found) print "unknown" }
        ' /mnt/etc/passwd 2>/dev/null || echo "unknown")
        if [[ "$OLD_UID" != "unknown" ]]; then
            info "从旧 /etc/passwd 推算旧 UID: $OLD_UID"
        else
            warn "无法从旧系统获取 UID，将跳过 chown 步骤。"
            SKIP_UID_CHECK=true
        fi
    fi
else
    # 直接用旧目录上的 uid
    OLD_UID=$(stat -c '%u' "$OLD_USER_DIR" 2>/dev/null || echo "unknown")
    info "从旧目录获取 UID: $OLD_UID"
fi

if [[ "$SKIP_UID_CHECK" != true ]] && [[ "$NEW_UID" != "$OLD_UID" ]]; then
    warn ""
    warn "⚠️  UID 不匹配！"
    warn "  新系统 UID: $NEW_UID（旧系统当前用户: $CURRENT_USER）"
    warn "  旧系统 UID: $OLD_UID（旧系统用户目录所有者）"
    warn ""
    warn "迁移后将对 /home/$CURRENT_USER 下的所有文件执行:"
    warn "  sudo chown -R $CURRENT_USER:$CURRENT_USER /home/$CURRENT_USER"
    warn "这样可以确保文件归属正确，但会丢失旧系统里其他用户的文件归属记录。"
    warn ""
    read -rp "继续？[y/N] " -n 1 confirm
    echo
    if [[ ! $confirm =~ ^[Yy]$ ]]; then
        error "用户中止。"
        exit 1
    fi
    DO_CHOWN=true
else
    DO_CHOWN=false
    info "UID 一致，无需 chown。"
fi

# ── 步骤 3: 备份 & rsync 迁移 ───────────────────────────
section "步骤 3 · 迁移用户数据"

# 需要排除的目录（缓存/临时/机器相关）
EXCLUDE_PATTERN_FILE=$(mktemp)
cat > "$EXCLUDE_PATTERN_FILE" << 'EXCLUDE_EOF'
# 系统缓存
- .cache/
- .local/share/Trash/
- .local/share/Trash-1000/
- */.cache/
- */Cache/
- */cache/

# 包管理器缓存
- node_modules/
- .npm/_cacache/
- .yarn/cache/
- .pnpm-store/
- .venv/
- venv/
- __pycache__/
- .pytest_cache/
- .mypy_cache/
- .tox/

# IDE 临时文件
- .vscode-server/data/Cache/
- .vscode/extensions/**/out/
- .idea/dataSources/
- .idea/caches/
- .gradle/caches/

# 浏览器工作缓存
- .config/chromium/Default/Cache/
- .config/google-chrome/Default/Cache/
- .config/google-chrome/Default/Code\ Cache/
- .config/microsoft-edge/Default/Cache/

# 机器特定文件
- .local/share/recently-used.xbel
- .local/share/gvfs-metadata/
- .config/gvfs/

# 大文件/下载物（建议手动整理）
- Downloads/
- Desktop/

EXCLUDE_EOF

info "排除目录列表（详见 $EXCLUDE_PATTERN_FILE）"
info "注意: Downloads/ 和 Desktop/ 被排除，建议手动复制大文件。\n"

read -rp "是否包含 Downloads 和 Desktop？（包含请输入 y，手动复制请输入 n）[y/N] " incl_dd
echo

if [[ $incl_dd =~ ^[Yy]$ ]]; then
    # 把排除的下载和桌面目录改回包含
    sed -i '/^- Downloads/d; /^- Desktop/d' "$EXCLUDE_PATTERN_FILE"
    info "将包含 Downloads 和 Desktop 目录。"
fi

info "开始 rsync 同步（预览模式，先只显示要复制的文件）..."
info "  源: $OLD_USER_DIR/"
info "  目标: $CURRENT_HOME/"
echo

# dry-run 预览
rsync -avn --exclude-from="$EXCLUDE_PATTERN_FILE" \
    "$OLD_USER_DIR/" "$CURRENT_HOME/" | head -80

echo
read -rp "↑ 预览结束，确认执行正式迁移？[y/N] " -n 1 confirm
echo

if [[ ! $confirm =~ ^[Yy]$ ]]; then
    error "用户中止。"
    rm -f "$EXCLUDE_PATTERN_FILE"
    exit 1
fi

info "开始迁移（这可能需要几分钟，请耐心等待）..."

rsync -av --exclude-from="$EXCLUDE_PATTERN_FILE" \
    --progress \
    --partial \
    "$OLD_USER_DIR/" "$CURRENT_HOME/"

rm -f "$EXCLUDE_PATTERN_FILE"

# ── 步骤 4: chown（如需要） ─────────────────────────────
section "步骤 4 · 修复文件归属"

if [[ "$DO_CHOWN" == true ]]; then
    info "正在 chown，这可能需要一点时间..."
    sudo chown -R "$CURRENT_USER:$CURRENT_USER" "$CURRENT_HOME"
    info "归属修复完成。"
else
    info "跳过（UID一致）。"
fi

# ── 步骤 5: 导出旧系统软件包 ─────────────────────────────
section "步骤 5 · 软件包迁移"

EXPORT_FILE="$CURRENT_HOME/.migrate_packages_$(date +%Y%m%d).txt"

# 收集 apt 包
info "导出 apt 包列表..."
dpkg --get-selections > "$EXPORT_FILE" 2>/dev/null

# 收集 snap 包
SNAP_FILE="${EXPORT_FILE%.txt}_snaps.txt"
snap list --all | awk 'NR>1 {print $1}' > "$SNAP_FILE" 2>/dev/null || true

# 收集 pip 包
PIP_FILE="${EXPORT_FILE%.txt}_pip.txt"
pip3 list --format=freeze 2>/dev/null > "${PIP_FILE}" || true

# 收集 npm 全局包
NPM_FILE="${EXPORT_FILE%.txt}_npm.txt"
npm list -g --depth=0 2>/dev/null | grep -v '^npm' > "${NPM_FILE}" || true

info "软件包清单已导出到:"
info "  $EXPORT_FILE（apt 包，请 root 执行: dnf @$(basename $EXPORT_FILE) 或 dpkg --set-selections < $EXPORT_FILE）"
info "  $SNAP_FILE（snap 包）"
info "  $PIP_FILE（pip 包）"
info "  $NPM_FILE（npm 全局包）"
echo
warn "⚠️  建议在新系统联网后执行以下命令安装软件:"
echo "    # apt 包（通用 Linux 软件）"
echo "    sudo dpkg --set-selections < $EXPORT_FILE"
echo "    sudo apt-get dselect-upgrade"
echo ""
echo "    # snap 包（需手动逐个: snap install \$(cat $SNAP_FILE)）"
echo "    # pip 包（需手动: pip3 install -r $PIP_FILE）"
echo "    # npm 包（需手动: npm install -g \$(cat $NPM_FILE)）"

# ── 步骤 6: SSH 密钥提示 ─────────────────────────────────
section "步骤 6 · SSH 密钥检查"

if [[ -f "$CURRENT_HOME/.ssh/id_rsa" ]] || [[ -f "$CURRENT_HOME/.ssh/id_ed25519" ]]; then
    info "检测到 SSH 私钥，请记得检查 ~/.ssh/config 和 known_hosts 是否需要更新。"
else
    info "未检测到 SSH 私钥，跳过。"
fi

# ── 完成 ─────────────────────────────────────────────────
section "迁移完成 ✓"

cat << 'EOF'

注意事项:
  1. 软件包只是导出了清单，需要在新系统联网后手动安装
  2. 建议重启电脑，让所有配置生效
  3. 如果使用 RStudio，可能需要重新配置 R 库路径
  4. 浏览器第一次启动时会要求解锁密钥环（密码默认 = 登录密码）
  5. /etc/fstab 中的 UUID 是旧的，如 home 挂载异常需重新配置
EOF
