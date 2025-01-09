#!/usr/bin/env python3
import fcntl
import struct
import os
import time
import select
import ctypes
from ctypes import Structure, c_uint32, c_uint8, c_long, create_string_buffer

# V4L2 and UVC constants
VIDIOC_SUBSCRIBE_EVENT = 0x4020565a
VIDIOC_DQEVENT = 0x8010565d  # We'll verify this value
UVCIOC_SEND_RESPONSE = 0x40087544

# UVC event types
UVC_EVENT_SETUP = 0x08000004
UVC_EVENT_DATA = 0x08000005
UVC_EVENT_STREAMON = 0x08000002
UVC_EVENT_STREAMOFF = 0x08000003

class timeval(Structure):
    _fields_ = [
        ('tv_sec', c_long),
        ('tv_usec', c_long)
    ]

class v4l2_event(Structure):
    _fields_ = [
        ('type', c_uint32),
        ('u', c_uint8 * 64),
        ('pending', c_uint32),
        ('sequence', c_uint32),
        ('timestamp', timeval),
        ('id', c_uint32),
        ('reserved', c_uint32 * 8)
    ]
    
def hex_dump(data, length=16):
    # Create a hex dump of binary data
    hex_str = ' '.join(f'{b:02x}' for b in data)
    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)
    return f"{hex_str.ljust(length*3)}  {ascii_str}"

def subscribe_event(fd, event_type):
    class v4l2_event_subscription(Structure):
        _fields_ = [
            ('type', c_uint32),
            ('id', c_uint32),
            ('flags', c_uint32),
            ('reserved', c_uint32 * 5)
        ]
    
    sub = v4l2_event_subscription()
    sub.type = event_type
    sub.id = 0
    sub.flags = 0
    
    try:
        fcntl.ioctl(fd, VIDIOC_SUBSCRIBE_EVENT, sub)
        print(f"Subscribed to event 0x{event_type:08x}")
        print(f"Subscription structure:")
        sub_bytes = bytes(sub)
        for i in range(0, len(sub_bytes), 16):
            print(f"  {hex_dump(sub_bytes[i:i+16])}")
    except Exception as e:
        print(f"Subscribe error for event 0x{event_type:08x}: {e}")
        raise

def handle_event(fd):
    # Try both the structured and raw approaches
    
    # 1. First try with raw buffer
    raw_buffer = create_string_buffer(256)  # Larger than we need
    try:
        print("\nAttempting raw buffer dequeue...")
        fcntl.ioctl(fd, VIDIOC_DQEVENT, raw_buffer)
        print("Raw buffer content:")
        for i in range(0, 128, 16):  # Print first 128 bytes
            print(f"  {hex_dump(raw_buffer.raw[i:i+16])}")
            
    except Exception as e:
        print(f"Raw buffer dequeue failed: {e}")
    
    # 2. Then try with structure
    event = v4l2_event()
    try:
        print("\nAttempting structured dequeue...")
        fcntl.ioctl(fd, VIDIOC_DQEVENT, event)
        print(f"Event type: 0x{event.type:08x}")
        print("Event structure content:")
        event_bytes = bytes(event)
        for i in range(0, len(event_bytes), 16):
            print(f"  {hex_dump(event_bytes[i:i+16])}")
            
    except Exception as e:
        print(f"Structured dequeue failed: {e}")
        print(f"Event structure size: {ctypes.sizeof(event)}")
        print(f"Event memory layout:")
        for name, type_ in event._fields_:
            offset = getattr(event.__class__, name).offset
            size = ctypes.sizeof(type_)
            print(f"  {name}: offset={offset}, size={size}")

def main():
    try:
        device_path = "/dev/video0"
        print(f"Opening {device_path}")
        fd = os.open(device_path, os.O_RDWR | os.O_NONBLOCK)
        
        # Subscribe to events
        event_types = [UVC_EVENT_SETUP, UVC_EVENT_DATA, UVC_EVENT_STREAMON, UVC_EVENT_STREAMOFF]
        for event_type in event_types:
            subscribe_event(fd, event_type)

        print("\nDevice ready - starting event loop")
        print("Structure sizes:")
        print(f"v4l2_event: {ctypes.sizeof(v4l2_event)}")
        print(f"timeval: {ctypes.sizeof(timeval)}")
        
        poll = select.poll()
        poll.register(fd, select.POLLIN | select.POLLPRI)
        
        while True:
            events = poll.poll(1000)
            if events:
                for fd, event_mask in events:
                    print(f"\nReceived event with mask: 0x{event_mask:04x}")
                    handle_event(fd)
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        if 'fd' in locals():
            os.close(fd)
            print("Closed device")

if __name__ == "__main__":
    main()
