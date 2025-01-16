#!/usr/bin/env python3
import os
import subprocess

def get_ioctl_value(name):
    c_code = f"""
    #include <linux/videodev2.h>
    #include <linux/usb/g_uvc.h>
    #include <stdio.h>
    int main() {{
        printf("0x%08x\\n", {name});
        return 0;
    }}
    """
    
    # Write code to temporary file
    with open('/tmp/check_ioctl.c', 'w') as f:
        f.write(c_code)
    
    # Compile and run
    try:
        subprocess.run(['gcc', '/tmp/check_ioctl.c', '-o', '/tmp/check_ioctl'])
        result = subprocess.run(['/tmp/check_ioctl'], capture_output=True, text=True)
        return result.stdout.strip()
    except Exception as e:
        return f"Error: {e}"
    finally:
        # Cleanup
        if os.path.exists('/tmp/check_ioctl'):
            os.remove('/tmp/check_ioctl')
        if os.path.exists('/tmp/check_ioctl.c'):
            os.remove('/tmp/check_ioctl.c')

print("Checking system IOCTL values...")
print(f"VIDIOC_DQEVENT = {get_ioctl_value('VIDIOC_DQEVENT')}")
print(f"VIDIOC_S_FMT = {get_ioctl_value('VIDIOC_S_FMT')}")
print(f"VIDIOC_SUBSCRIBE_EVENT = {get_ioctl_value('VIDIOC_SUBSCRIBE_EVENT')}")
print(f"UVCIOC_SEND_RESPONSE = {get_ioctl_value('UVCIOC_SEND_RESPONSE')}")

# Let's also directly calculate it based on the macro from g_uvc.h
# From g_uvc.h: #define UVCIOC_SEND_RESPONSE      _IOW('U', 1, struct uvc_request_data)
import struct

def _IOW(type, nr, size):
    # Linux ioctl encoding: direction | size | type | nr
    IOC_WRITE = 1 << 30
    IOC_SIZEBITS = 14
    IOC_TYPEBITS = 8
    
    return IOC_WRITE | (size & ((1 << IOC_SIZEBITS) - 1)) << 16 | (ord(type) << 8) | nr

# Calculate size of uvc_request_data (length:int32 + data:uint8[60])
size = struct.calcsize('i60B')  # 4 + 60 = 64 bytes
calculated_code = _IOW('U', 1, size)
print(f"\nCalculated UVCIOC_SEND_RESPONSE = 0x{calculated_code:08x}")
