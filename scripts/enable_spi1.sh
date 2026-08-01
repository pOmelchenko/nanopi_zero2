#!/usr/bin/env bash

# Build a minimal FriendlyElec resource.img with SPI1/spidev enabled for the
# NanoPi Zero2. The optional --touch mode also binds the XPT2046 on SPI1 CS1
# through the in-tree ads7846 driver. By default this script only builds and
# verifies the image. Pass --install to write the resource partition, and
# --reboot to reboot after a verified write.

set -Eeuo pipefail

readonly KERNEL_REPOSITORY="https://github.com/friendlyarm/kernel-rockchip.git"
readonly KERNEL_COMMIT="221af17f44d3b513b53b694d5b41614e53c5ab1b"
readonly DTB_NAME="rk3528-nanopi-rev01.dtb"
readonly DTB_TARGET="rockchip/${DTB_NAME}"
readonly SPI_NODE="/spi@ff9d0000"
readonly DEFAULT_WORK_DIR="/var/lib/nanopi-zero2-spi1"

install_image=0
reboot_after_install=0
touch_enabled=0
work_dir="$DEFAULT_WORK_DIR"
patch_applied=0
patch_file=""
kernel_dir=""

usage() {
    cat <<'EOF'
Usage: sudo ./enable_spi1.sh [OPTIONS]

Build and verify a FriendlyElec NanoPi Zero2 resource.img with SPI1 enabled.
The default display-only mode does not write eMMC or enable a floating touch
IRQ. Use --touch only after wiring the XPT2046 header, including T_IRQ.

Options:
  --install          back up and write the resource partition
  --reboot           reboot after a successful --install
  --touch            also enable XPT2046 on CS1 and ads7846 autoload
  --work-dir PATH    persistent build/output directory
  -h, --help         show this help

Examples:
  sudo ./enable_spi1.sh
  sudo ./enable_spi1.sh --install --reboot
  sudo ./enable_spi1.sh --touch --install --reboot
EOF
}

log() {
    printf '\n==> %s\n' "$*"
}

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

restore_kernel_source() {
    if ((patch_applied)) && [[ -n "$kernel_dir" && -n "$patch_file" ]]; then
        if git -C "$kernel_dir" apply -R "$patch_file"; then
            patch_applied=0
        else
            printf 'WARNING: could not reverse the temporary DTS patch in %s\n' \
                "$kernel_dir" >&2
        fi
    fi
}

trap restore_kernel_source EXIT

while (($#)); do
    case "$1" in
        --install)
            install_image=1
            ;;
        --reboot)
            reboot_after_install=1
            ;;
        --touch)
            touch_enabled=1
            ;;
        --work-dir)
            shift
            (($#)) || die "--work-dir requires a path"
            work_dir="$1"
            ;;
        -h | --help)
            usage
            exit 0
            ;;
        *)
            die "unknown argument: $1"
            ;;
    esac
    shift
done

((reboot_after_install == 0 || install_image == 1)) || \
    die "--reboot requires --install"
[[ ${EUID:-$(id -u)} -eq 0 ]] || die "run this script through sudo or as root"
[[ -r /etc/friendlyelec-release ]] || die "not a FriendlyElec system"
grep -q 'NanoPi-Zero2' /etc/friendlyelec-release || \
    die "this script supports only NanoPi Zero2"
[[ -r /proc/device-tree/model ]] || die "Device Tree model is unavailable"
[[ "$(tr -d '\0' </proc/device-tree/model)" == "FriendlyElec NanoPi Zero2" ]] || \
    die "unexpected board model: $(tr -d '\0' </proc/device-tree/model)"
[[ -d "/proc/device-tree${SPI_NODE}" ]] || die "SPI1 Device Tree node is missing"

current_spi_status="$(tr -d '\0' <"/proc/device-tree${SPI_NODE}/status")"
touch_node="/proc/device-tree${SPI_NODE}/touchscreen@1"
if [[ "$current_spi_status" == "okay" && -c /dev/spidev1.0 && \
      (touch_enabled -eq 0 || -d "$touch_node") ]]; then
    log "SPI1 is already enabled"
    if ((touch_enabled)); then
        install -D -o root -g root -m 0644 /dev/stdin \
            /etc/modules-load.d/nanopi-xpt2046.conf <<<'ads7846'
        printf '/dev/spidev1.0 and the XPT2046 Device Tree node are ready.\n'
        printf 'ads7846 autoload was ensured; reboot if the input device is absent.\n'
    else
        printf '/dev/spidev1.0 is ready; no changes were made.\n'
    fi
    exit 0
fi

mapfile -t resource_targets < <(
    lsblk -rpn -o PATH,PARTLABEL | awk '$2 == "resource" { print $1 }'
)
((${#resource_targets[@]} == 1)) || \
    die "expected exactly one PARTLABEL=resource partition"
readonly resource_target="${resource_targets[0]}"
[[ "$(lsblk -n -o PARTLABEL "$resource_target")" == "resource" ]] || \
    die "resolved partition does not have PARTLABEL=resource"
readonly resource_size="$(blockdev --getsize64 "$resource_target")"
((resource_size > 0)) || die "resource partition has an invalid size"

install -d -m 0700 "$work_dir" "$work_dir/runs" "$work_dir/backups"
readonly run_dir="$(mktemp -d "$work_dir/runs/run.XXXXXXXX")"
kernel_dir="$work_dir/kernel-rk3528"
patch_file="$run_dir/official-friendlyelec-spi1.patch"
readonly original_image="$run_dir/resource.img.original"
if ((touch_enabled)); then
    readonly output_image="$run_dir/resource.img.spi-touch"
else
    readonly output_image="$run_dir/resource.img.spi"
fi
readonly readback_image="$run_dir/resource.img.readback"
readonly original_dir="$run_dir/resource-original-unpacked"
readonly verified_dir="$run_dir/resource-new-unpacked"

log "Backing up the current resource partition"
dd if="$resource_target" of="$original_image" \
    bs=1M status=progress conv=fsync
[[ "$(stat -c %s "$original_image")" -eq "$resource_size" ]] || \
    die "resource backup size mismatch"
sha256sum "$original_image"

log "Installing native build dependencies"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
    bc bison build-essential device-tree-compiler flex git \
    libelf-dev libssl-dev rsync u-boot-tools

log "Preparing the pinned FriendlyElec kernel source"
if [[ ! -e "$kernel_dir" ]]; then
    git init "$kernel_dir"
    git -C "$kernel_dir" remote add origin "$KERNEL_REPOSITORY"
    git -C "$kernel_dir" fetch --depth 1 origin "$KERNEL_COMMIT"
    git -C "$kernel_dir" checkout --detach FETCH_HEAD
fi
[[ -d "$kernel_dir/.git" ]] || die "$kernel_dir exists but is not a Git checkout"
[[ "$(git -C "$kernel_dir" rev-parse HEAD)" == "$KERNEL_COMMIT" ]] || \
    die "kernel checkout is not at the required commit $KERNEL_COMMIT"
git -C "$kernel_dir" diff --quiet || die "kernel checkout has unstaged changes"
git -C "$kernel_dir" diff --cached --quiet || die "kernel checkout has staged changes"

if ((touch_enabled)); then
    cat >"$patch_file" <<'PATCH'
diff --git a/arch/arm64/boot/dts/rockchip/rk3528-nanopi-rev01.dts b/arch/arm64/boot/dts/rockchip/rk3528-nanopi-rev01.dts
--- a/arch/arm64/boot/dts/rockchip/rk3528-nanopi-rev01.dts
+++ b/arch/arm64/boot/dts/rockchip/rk3528-nanopi-rev01.dts
@@ -65,6 +65,52 @@ &mach {
 	model = "NanoPi Zero2";
 };
 
+&spi1 {
+	#address-cells = <1>;
+	#size-cells = <0>;
+	num-cs = <2>;
+
+	pinctrl-names = "default";
+	pinctrl-0 = <&spi1_pins &spi1_csn0 &spi1_csn1>;
+	status = "okay";
+
+	spidev@0 {
+		compatible = "rohm,dh2228fv";
+		reg = <0>;
+		spi-max-frequency = <10000000>;
+	};
+
+	touchscreen@1 {
+		compatible = "ti,tsc2046";
+		reg = <1>;
+		pinctrl-names = "default";
+		pinctrl-0 = <&touch_irq_pin>;
+		interrupt-parent = <&gpio4>;
+		interrupts = <RK_PA4 IRQ_TYPE_EDGE_FALLING>;
+		spi-max-frequency = <1000000>;
+		pendown-gpio = <&gpio4 RK_PA4 GPIO_ACTIVE_LOW>;
+		vcc-supply = <&vcc_3v3_s3>;
+		ti,x-min = /bits/ 16 <250>;
+		ti,x-max = /bits/ 16 <3800>;
+		ti,y-min = /bits/ 16 <350>;
+		ti,y-max = /bits/ 16 <3650>;
+		ti,x-plate-ohms = /bits/ 16 <400>;
+		ti,pressure-max = /bits/ 16 <2000>;
+		ti,debounce-max = /bits/ 16 <10>;
+		ti,debounce-tol = /bits/ 16 <50>;
+		ti,debounce-rep = /bits/ 16 <2>;
+		touchscreen-inverted-x;
+	};
+};
+
+&pinctrl {
+	touchscreen {
+		touch_irq_pin: touch-irq-pin {
+			rockchip,pins = <4 RK_PA4 RK_FUNC_GPIO &pcfg_pull_up>;
+		};
+	};
+};
+
 &gmac1 {
 	/* Use rgmii-rxid mode to disable rx delay inside Soc */
 	phy-mode = "rgmii-rxid";
PATCH
else
    cat >"$patch_file" <<'PATCH'
diff --git a/arch/arm64/boot/dts/rockchip/rk3528-nanopi-rev01.dts b/arch/arm64/boot/dts/rockchip/rk3528-nanopi-rev01.dts
--- a/arch/arm64/boot/dts/rockchip/rk3528-nanopi-rev01.dts
+++ b/arch/arm64/boot/dts/rockchip/rk3528-nanopi-rev01.dts
@@ -66,3 +66,18 @@
 };
-
+
+&spi1 {
+	#address-cells = <1>;
+	#size-cells = <0>;
+
+	pinctrl-names = "default";
+	pinctrl-0 = <&spi1_pins &spi1_csn0>;
+	status = "okay";
+
+	spidev@0 {
+		compatible = "rohm,dh2228fv";
+		reg = <0>;
+		spi-max-frequency = <10000000>;
+	};
+};
+
 &gmac1 {
PATCH
fi

log "Building the unmodified DTB and Rockchip resource_tool"
make -C "$kernel_dir" ARCH=arm64 nanopi6_linux_defconfig
make -C "$kernel_dir" -j"$(nproc)" ARCH=arm64 "$DTB_TARGET"
make -C "$kernel_dir" -j"$(nproc)" ARCH=arm64 scripts
readonly resource_tool="$kernel_dir/scripts/resource_tool"
[[ -x "$resource_tool" ]] || die "resource_tool was not built"

"$resource_tool" --unpack --image="$original_image" "$original_dir"
readonly factory_dtb="$original_dir/$DTB_NAME"
readonly built_dtb="$kernel_dir/arch/arm64/boot/dts/rockchip/$DTB_NAME"
[[ -f "$factory_dtb" ]] || die "$DTB_NAME is missing from the current resource image"

log "Verifying that source and factory DTBs are byte-identical"
cmp "$built_dtb" "$factory_dtb" || \
    die "factory DTB differs from the pinned clean source; refusing to continue"
sha256sum "$factory_dtb" "$built_dtb"

if ((touch_enabled)); then
    log "Applying the SPI1 display-and-touch DTS patch"
else
    log "Applying the SPI1 display-only DTS patch"
fi
git -C "$kernel_dir" apply --check "$patch_file"
git -C "$kernel_dir" apply "$patch_file"
patch_applied=1
git -C "$kernel_dir" diff --check
make -C "$kernel_dir" -j"$(nproc)" ARCH=arm64 "$DTB_TARGET"
cp "$built_dtb" "$factory_dtb"

log "Packing and independently verifying the new resource image"
(
    cd "$original_dir"
    "$resource_tool" --dtbname --pack --image="$output_image" *
)
[[ "$(stat -c %s "$output_image")" -le "$resource_size" ]] || \
    die "packed resource image is larger than the partition"
truncate -s "$resource_size" "$output_image"
"$resource_tool" --unpack --image="$output_image" "$verified_dir"

while IFS= read -r -d '' original_file; do
    file_name="${original_file##*/}"
    [[ -f "$verified_dir/$file_name" ]] || die "packed image lost $file_name"
    cmp "$original_file" "$verified_dir/$file_name" || \
        die "packed image changed $file_name unexpectedly"
done < <(find "$original_dir" -maxdepth 1 -type f -print0)

[[ "$(fdtget "$verified_dir/$DTB_NAME" "$SPI_NODE" status)" == "okay" ]] || \
    die "SPI1 status is not okay in the packed image"
[[ "$(fdtget "$verified_dir/$DTB_NAME" "$SPI_NODE/spidev@0" compatible)" == \
    "rohm,dh2228fv" ]] || die "spidev@0 is missing from the packed image"
[[ "$(fdtget "$verified_dir/$DTB_NAME" "$SPI_NODE/spidev@0" \
    spi-max-frequency)" == "10000000" ]] || die "unexpected SPI maximum frequency"

if ((touch_enabled)); then
    readonly touch_dtb_node="$SPI_NODE/touchscreen@1"
    [[ "$(fdtget "$verified_dir/$DTB_NAME" "$SPI_NODE" num-cs)" == "2" ]] || \
        die "SPI1 does not expose two chip selects"
    [[ "$(fdtget "$verified_dir/$DTB_NAME" "$touch_dtb_node" compatible)" == \
        "ti,tsc2046" ]] || die "XPT2046 node is missing from the packed image"
    [[ "$(fdtget "$verified_dir/$DTB_NAME" "$touch_dtb_node" reg)" == "1" ]] || \
        die "XPT2046 is not assigned to SPI1 CS1"
    [[ "$(fdtget "$verified_dir/$DTB_NAME" "$touch_dtb_node" \
        spi-max-frequency)" == "1000000" ]] || \
        die "unexpected XPT2046 SPI maximum frequency"
    touch_properties="$(fdtget -p "$verified_dir/$DTB_NAME" "$touch_dtb_node")"
    for property in interrupts pendown-gpio vcc-supply ti,x-min ti,x-max \
        ti,y-min ti,y-max ti,pressure-max touchscreen-inverted-x; do
        grep -qx "$property" <<<"$touch_properties" || \
            die "XPT2046 property $property is missing"
    done
fi

sha256sum "$output_image"
printf '\nVerified image: %s\n' "$output_image"

if ((install_image == 0)); then
    printf '%s\n' \
        'Build-only mode: the eMMC resource partition was not changed.' \
        'Run the same script with --install to back up and install this configuration.'
    exit 0
fi

log "Saving a persistent pre-install backup"
readonly timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
if ((touch_enabled)); then
    readonly persistent_backup="$work_dir/backups/resource.before-spi-touch.${timestamp}.img"
else
    readonly persistent_backup="$work_dir/backups/resource.before-spi.${timestamp}.img"
fi
install -m 0600 "$original_image" "$persistent_backup"
sha256sum "$persistent_backup"

log "Writing only the validated PARTLABEL=resource partition"
[[ "$(lsblk -n -o PARTLABEL "$resource_target")" == "resource" ]] || \
    die "resource partition label changed before write"
dd if="$output_image" of="$resource_target" \
    bs=1M status=progress conv=fsync
sync
dd if="$resource_target" of="$readback_image" \
    bs=1M status=none
cmp "$output_image" "$readback_image" || die "resource readback verification failed"
sha256sum "$output_image" "$readback_image"

restore_kernel_source
trap - EXIT

if ((touch_enabled)); then
    install -D -o root -g root -m 0644 /dev/stdin \
        /etc/modules-load.d/nanopi-xpt2046.conf <<<'ads7846'
    printf '\nSPI1 display-and-touch resource image installed successfully.\n'
    printf 'ads7846 autoload: /etc/modules-load.d/nanopi-xpt2046.conf\n'
else
    printf '\nSPI1 display-only resource image installed successfully.\n'
fi
printf 'Recovery backup: %s\n' "$persistent_backup"

if ((reboot_after_install)); then
    log "Rebooting"
    systemctl reboot
else
    printf 'Reboot is required. After boot, verify /dev/spidev1.0'
    if ((touch_enabled)); then
        printf ' and ADS7846 Touchscreen'
    fi
    printf '.\n'
fi
