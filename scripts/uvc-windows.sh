#!/bin/bash
###############################################################################
# snake_cam_emulation.sh
#
# Emulates a UVC device (USB Video Class) based on the USBlyzer snake cam report.
###############################################################################

set -e  # Exit on any error
set -x

# Check for root privileges
if [ "$(id -u)" -ne 0 ]; then
    echo "Please run this script as root (e.g., sudo $0)."
    exit 1
fi

create_frame() {
	# Example usage:
	# create_frame <width> <height> <group> <format name>

	FUNCTION_PATH=$1
	WIDTH=$2
	HEIGHT=$3
	FORMAT=$4
	NAME=$5

	#wdir=$FUNCTION_PATH/streaming/$FORMAT/$NAME/${HEIGHT}p
	wdir=$FUNCTION_PATH/streaming/$FORMAT/$NAME/${WIDTH}x${HEIGHT}

	mkdir -p $wdir
	echo $WIDTH | sudo tee $wdir/wWidth > /dev/null
	echo $HEIGHT | sudo tee $wdir/wHeight > /dev/null
	
	# echo $(( $WIDTH * $HEIGHT * 2 )) | sudo tee $wdir/dwMaxVideoFrameBufferSize > /dev/null
	echo 500000 | sudo tee $wdir/dwDefaultFrameInterval > /dev/null
	cat <<EOF > $wdir/dwFrameInterval
166666
200000
333333
500000
EOF

	echo $(( $WIDTH * $HEIGHT * 80 )) | sudo tee $wdir/dwMinBitRate > /dev/null
	echo $(( $WIDTH * $HEIGHT * 160 )) | sudo tee $wdir/dwMaxBitRate > /dev/null
}

# Load required kernel modules
sudo modprobe dwc2
sudo modprobe libcomposite
sudo modprobe usb_f_uvc

# Create gadget directory
echo "=== Creating New Gadget Directory ==="
mkdir -p /sys/kernel/config/usb_gadget/uvc_gadget
cd /sys/kernel/config/usb_gadget/uvc_gadget

###############################################################################
# Device-level descriptors: single-interface HID
###############################################################################
echo 0x038F | sudo tee idVendor > /dev/null        # Vendor ID
echo 0x6001 | sudo tee idProduct > /dev/null      # Product ID

echo "super-speed" | sudo tee max_speed > /dev/null
echo 64 | sudo tee bMaxPacketSize0 > /dev/null

echo 0x0100 | sudo tee bcdDevice > /dev/null      # Device version
echo 0x0200 | sudo tee bcdUSB > /dev/null         # USB 2.0

echo 0xEF | sudo tee bDeviceClass > /dev/null
echo 0x02 | sudo tee bDeviceSubClass > /dev/null
echo 0x01 | sudo tee bDeviceProtocol > /dev/null



###############################################################################
# Strings (English - 0x409)
###############################################################################
mkdir -p strings/0x409
echo "1234567890" | sudo tee strings/0x409/serialnumber > /dev/null   # Exact serial number
echo "BVR Manuf" | sudo tee strings/0x409/manufacturer > /dev/null # Exact manufacturer
echo "My USB2.0 Camera" | sudo tee strings/0x409/product > /dev/null      # Exact product name

###############################################################################
# Configuration (c.1)
###############################################################################
mkdir -p configs/c.1/strings/0x409
echo 0x80 | sudo tee configs/c.1/bmAttributes > /dev/null  # Bus powered
echo 500 | sudo tee configs/c.1/MaxPower > /dev/null
echo "UVC" | sudo tee configs/c.1/strings/0x409/configuration > /dev/null

# create UVC function
mkdir -p functions/uvc.0
mkdir -p functions/uvc.0/control/header/h

echo 2048 | sudo tee functions/uvc.0/streaming_maxpacket > /dev/null  # Max packet size for isochronous
echo 1 | sudo tee functions/uvc.0/streaming_interval > /dev/null  # Max packet size for isochronous

# High-Speed (HS) and Full-Speed (FS) links
ln -sf functions/uvc.0/control/header/h functions/uvc.0/control/class/fs
ln -sf functions/uvc.0/control/header/h functions/uvc.0/control/class/ss

mkdir -p functions/uvc.0/streaming/uncompressed/u
create_frame functions/uvc.0 640 360 uncompressed u
create_frame functions/uvc.0 1280 720 uncompressed u
create_frame functions/uvc.0 1920 1080 uncompressed u

mkdir -p functions/uvc.0/streaming/mjpeg/m
create_frame functions/uvc.0 640 360 mjpeg m
create_frame functions/uvc.0 1280 720 mjpeg m
create_frame functions/uvc.0 1920 1080 mjpeg m

mkdir -p functions/uvc.0/streaming/header/h

# Configure Control Interface
ln -sf functions/uvc.0/streaming/uncompressed/u functions/uvc.0/streaming/header/h

# Configure Streaming Interface
ln -sf functions/uvc.0/streaming/header/h functions/uvc.0/streaming/class/fs
ln -sf functions/uvc.0/streaming/header/h functions/uvc.0/streaming/class/hs
ln -sf functions/uvc.0/streaming/header/h functions/uvc.0/streaming/class/ss

# Link UVC function to the configuration
ln -sf functions/uvc.0 configs/c.1/




# Bind to UDC (attach gadget)
UDC=$(ls /sys/class/udc | head -n 1)
if [ -z "$UDC" ]; then
    echo "No UDC found. Ensure USB controller is in gadget mode."
    exit 1
fi

echo "=== Waiting to settle ==="

udevadm settle -t 5 || :
sleep 2

echo "=== Binding gadget to $UDC ==="
echo "$UDC" | sudo tee UDC > /dev/null

echo "Snake cam UVC gadget configured successfully with exact descriptors!"

# ✅ Force the correct mode before checking formats
sudo v4l2-ctl --set-fmt-video=width=640,height=360,pixelformat=YUYV --device /dev/video0

# Verify that the format is set correctly
v4l2-ctl --list-formats-ext -d /dev/video0
# ioctl: VIDIOC_ENUM_FMT
#        Type: Video Capture
#
#        [0]: 'YUYV' (YUYV 4:2:2)
#                Size: Discrete 640x480
#                        Interval: Discrete 0.033s (30.00 fps)
#                        Interval: Discrete 0.066s (15.00 fps)
#                        Interval: Discrete 0.010s (100.00 fps)
#                        Interval: Discrete 5.000s (0.20 fps)
