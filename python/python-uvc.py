#!/usr/bin/env python3
import fcntl
import struct
import os
import time

# Exact values from C program output
VIDIOC_SUBSCRIBE_EVENT = 0x4020565a  # Value from C program

# Exact UVC event values from C program output
UVC_EVENT_SETUP = 0x08000004      # 134217732
UVC_EVENT_DATA = 0x08000005       # 134217733
UVC_EVENT_STREAMON = 0x08000002   # 134217730
UVC_EVENT_STREAMOFF = 0x08000003  # 134217731

def subscribe_event(fd, event_type):
    # Create 32-byte structure (size from C program output)
    # Format: I (type) + I (id) + I (flags) + i (reserved[0]) + 16s (reserved[1:])
    data = struct.pack('IIIi16s', 
        event_type,  # type - 4 bytes
        0,          # id - 4 bytes
        0,          # flags - 4 bytes
        0,          # reserved[0] - 4 bytes
        b'\0' * 16  # remaining reserved bytes to total 32 bytes
    )
    print(f"Subscribing to event 0x{event_type:08x}")
    fcntl.ioctl(fd, VIDIOC_SUBSCRIBE_EVENT, data)

def main():
    try:
        # Open the UVC device
        device_path = "/dev/video0"
        print(f"Opening {device_path}")
        fd = os.open(device_path, os.O_RDWR | os.O_NONBLOCK)
        
        # Subscribe to events in the same order as the C program
        event_types = [
            UVC_EVENT_SETUP,
            UVC_EVENT_DATA,
            UVC_EVENT_STREAMON,
            UVC_EVENT_STREAMOFF
        ]
        
        for event_type in event_types:
            try:
                subscribe_event(fd, event_type)
                print(f"Successfully subscribed to event 0x{event_type:08x}")
            except Exception as e:
                print(f"Failed to subscribe to event 0x{event_type:08x}: {e}")
                os.close(fd)
                return

        print("\nDevice should now be activated")
        print("Keep this program running to maintain the UVC device")
        print("Press Ctrl+C to exit")
        
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        if 'fd' in locals():
            os.close(fd)
            print("Closed device")

if __name__ == "__main__":
    main()
