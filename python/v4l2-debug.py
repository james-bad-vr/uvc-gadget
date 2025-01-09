#!/usr/bin/env python3
import fcntl
import os
import struct
from ctypes import *

def get_device_caps(fd):
    """Get device capabilities using VIDIOC_QUERYCAP"""
    # Define the v4l2_capability structure
    class v4l2_capability(Structure):
        _fields_ = [
            ('driver', c_char * 16),
            ('card', c_char * 32),
            ('bus_info', c_char * 32),
            ('version', c_uint32),
            ('capabilities', c_uint32),
            ('device_caps', c_uint32),
            ('reserved', c_uint32 * 3)
        ]
    
    cap = v4l2_capability()
    try:
        fcntl.ioctl(fd, 0x80685600, cap)  # VIDIOC_QUERYCAP
        print("\nDevice Capabilities:")
        print(f"Driver: {cap.driver.decode()}")
        print(f"Card: {cap.card.decode()}")
        print(f"Bus info: {cap.bus_info.decode()}")
        print(f"Version: 0x{cap.version:08x}")
        print(f"Capabilities: 0x{cap.capabilities:08x}")
        print(f"Device caps: 0x{cap.device_caps:08x}")
        return True
    except Exception as e:
        print(f"Failed to query capabilities: {e}")
        return False

def test_format_setting(fd):
    """Try different ways of setting the format"""
    print("\nTesting format setting...")
    
    # Define the format structure
    class v4l2_pix_format(Structure):
        _fields_ = [
            ('width', c_uint32),
            ('height', c_uint32),
            ('pixelformat', c_uint32),
            ('field', c_uint32),
            ('bytesperline', c_uint32),
            ('sizeimage', c_uint32),
            ('colorspace', c_uint32),
            ('priv', c_uint32),
            ('flags', c_uint32),
            ('ycbcr_enc', c_uint32),
            ('quantization', c_uint32),
            ('xfer_func', c_uint32),
        ]
    
    class v4l2_format(Structure):
        class _u(Union):
            class _fmt(Structure):
                _fields_ = [('pix', v4l2_pix_format)]
            _fields_ = [('fmt', _fmt)]
        _fields_ = [
            ('type', c_uint32),
            ('u', _u)
        ]
    
    fmt = v4l2_format()
    fmt.type = 2  # V4L2_BUF_TYPE_VIDEO_OUTPUT
    fmt.u.fmt.pix.width = 640
    fmt.u.fmt.pix.height = 360
    fmt.u.fmt.pix.pixelformat = 0x56595559  # V4L2_PIX_FMT_YUYV
    fmt.u.fmt.pix.field = 1  # V4L2_FIELD_NONE
    fmt.u.fmt.pix.bytesperline = 640 * 2
    fmt.u.fmt.pix.sizeimage = 640 * 360 * 2
    
    # Try different IOCTL values
    ioctl_values = [
        0xc0d05605,  # Our current value
        0x5605,      # Basic value
        0x40185605,  # Another common value
    ]
    
    for ioctl in ioctl_values:
        try:
            print(f"\nTrying IOCTL value: 0x{ioctl:08x}")
            fcntl.ioctl(fd, ioctl, fmt)
            print("Success!")
            return True
        except Exception as e:
            print(f"Failed: {e}")
    
    return False

def main():
    device = "/dev/video0"
    try:
        fd = os.open(device, os.O_RDWR | os.O_NONBLOCK)
        print(f"Opened {device}")
        
        if get_device_caps(fd):
            test_format_setting(fd)
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'fd' in locals():
            os.close(fd)
            print("\nDevice closed")

if __name__ == "__main__":
    main()
