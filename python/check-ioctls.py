#!/usr/bin/env python3
import os
import subprocess

def get_ioctl_value(name):
    c_code = f"""
    #include <linux/videodev2.h>
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
