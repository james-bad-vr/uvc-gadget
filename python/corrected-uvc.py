#!/usr/bin/env python3
import fcntl
import struct
import os
import time
import select
import ctypes
from ctypes import Structure, c_uint32, c_uint8, c_long, c_void_p, sizeof, addressof, POINTER

# Correct IOCTL values for your system
VIDIOC_SUBSCRIBE_EVENT = 0x4020565a
VIDIOC_DQEVENT = 0x80805659  # Updated to correct value
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

class v4l2_event_subscription(Structure):
    _fields_ = [
        ('type', c_uint32),
        ('id', c_uint32),
        ('flags', c_uint32),
        ('reserved', c_uint32 * 5)
    ]

class v4l2_event(Structure):
    class U(ctypes.Union):
        _fields_ = [
            ('data', c_uint8 * 64),
            ('payload64', c_uint32 * 16)
        ]
    
    _fields_ = [
        ('type', c_uint32),
        ('u', U),
        ('pending', c_uint32),
        ('sequence', c_uint32),
        ('timestamp', timeval),
        ('id', c_uint32),
        ('reserved', c_uint32 * 8)
    ]

def handle_setup_event(fd, data):
    bmRequestType, bRequest, wValue, wIndex, wLength = struct.unpack('<BBHHH', data)
    print(f"Setup Request:")
    print(f"  bmRequestType: 0x{bmRequestType:02x}")
    print(f"  bRequest: 0x{bRequest:02x}")
    print(f"  wValue: 0x{wValue:04x}")
    print(f"  wIndex: 0x{wIndex:04x}")
    print(f"  wLength: {wLength}")

    response_data = None
    if bmRequestType == 0xA1:  # Class-specific GET request
        if bRequest == 0x86:   # GET_INFO
            print("  -> GET_INFO request")
            response_data = struct.pack('<B', 0x03)  # GET/SET supported
        elif bRequest == 0x87:  # GET_DEF
            print("  -> GET_DEF request")
            response_data = struct.pack('<H', 0x007F)
        elif bRequest == 0x82:  # GET_MIN
            print("  -> GET_MIN request")
            response_data = struct.pack('<H', 0x0000)
        elif bRequest == 0x83:  # GET_MAX
            print("  -> GET_MAX request")
            response_data = struct.pack('<H', 0x00FF)
        elif bRequest == 0x84:  # GET_RES
            print("  -> GET_RES request")
            response_data = struct.pack('<H', 0x0001)

    if response_data:
        try:
            padded_response = response_data.ljust(64, b'\0')
            fcntl.ioctl(fd, UVCIOC_SEND_RESPONSE, padded_response)
            print("  -> Response sent successfully")
        except Exception as e:
            print(f"  -> Failed to send response: {e}")

def subscribe_event(fd, event_type):
    sub = v4l2_event_subscription()
    sub.type = event_type
    sub.id = 0
    sub.flags = 0
    fcntl.ioctl(fd, VIDIOC_SUBSCRIBE_EVENT, sub)
    print(f"Subscribed to event 0x{event_type:08x}")

def handle_event(fd):
    event = v4l2_event()
    try:
        event_p = ctypes.pointer(event)
        fcntl.ioctl(fd, VIDIOC_DQEVENT, event_p)
        
        print(f"Event received:")
        print(f"  Type: 0x{event.type:08x}")
        print(f"  Sequence: {event.sequence}")
        
        if event.type == UVC_EVENT_SETUP:
            handle_setup_event(fd, bytes(event.u.data[0:8]))
        elif event.type == UVC_EVENT_STREAMON:
            print("Stream ON event received")
        elif event.type == UVC_EVENT_STREAMOFF:
            print("Stream OFF event received")
            
    except Exception as e:
        print(f"Error handling event: {e}")
        print(f"Event structure size: {sizeof(event)}")
        print(f"Event address: {addressof(event):x}")

def main():
    try:
        device_path = "/dev/video0"
        print(f"Opening {device_path}")
        fd = os.open(device_path, os.O_RDWR | os.O_NONBLOCK)
        
        # Subscribe to events
        event_types = [UVC_EVENT_SETUP, UVC_EVENT_DATA, UVC_EVENT_STREAMON, UVC_EVENT_STREAMOFF]
        for event_type in event_types:
            subscribe_event(fd, event_type)

        print("\nDevice ready - waiting for events...")
        
        poll = select.poll()
        poll.register(fd, select.POLLIN | select.POLLPRI)
        
        while True:
            events = poll.poll(1000)
            if events:
                for fd, event_mask in events:
                    handle_event(fd)
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        if 'fd' in locals():
            os.close(fd)
            print("Device closed")

if __name__ == "__main__":
    main()
