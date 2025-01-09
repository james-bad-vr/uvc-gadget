#!/usr/bin/env python3
import fcntl
import struct
import os
import time
import select
import ctypes
from ctypes import Structure, c_uint32, c_uint8, c_long, sizeof, addressof, POINTER

# Constants from the C code
VIDIOC_SUBSCRIBE_EVENT = 0x4020565a
VIDIOC_DQEVENT = 0x80805659
UVCIOC_SEND_RESPONSE = 0x40087544

# Event flags from uvc.c
V4L2_EVENT_SUB_FL_SEND_INITIAL = 0x1
V4L2_EVENT_SUB_FL_ALLOW_FEEDBACK = 0x2

# UVC event types from uvc.h
UVC_EVENT_CONNECT = 0x08000000
UVC_EVENT_DISCONNECT = 0x08000001
UVC_EVENT_STREAMON = 0x08000002
UVC_EVENT_STREAMOFF = 0x08000003
UVC_EVENT_SETUP = 0x08000004
UVC_EVENT_DATA = 0x08000005

class timeval(Structure):
    _fields_ = [
        ('tv_sec', c_long),
        ('tv_usec', c_long)
    ]

class v4l2_event(Structure):
    class U(ctypes.Union):
        _fields_ = [
            ('data', c_uint8 * 64),
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

def subscribe_event(fd, event_type):
    sub = v4l2_event_subscription()
    sub.type = event_type
    sub.id = 0
    sub.flags = V4L2_EVENT_SUB_FL_SEND_INITIAL | V4L2_EVENT_SUB_FL_ALLOW_FEEDBACK
    
    try:
        fcntl.ioctl(fd, VIDIOC_SUBSCRIBE_EVENT, sub)
        print(f"Subscribed to event 0x{event_type:08x} with flags 0x{sub.flags:x}")
        sub_bytes = bytes(sub)
        print(f"Subscription data: {' '.join(f'{b:02x}' for b in sub_bytes[:16])}")
    except Exception as e:
        print(f"Failed to subscribe to event 0x{event_type:08x}: {e}")
        raise

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
            print(f"  -> Response sent: {' '.join(f'{b:02x}' for b in padded_response[:len(response_data)])}")
        except Exception as e:
            print(f"  -> Failed to send response: {e}")
            print(f"  -> Response data length: {len(padded_response)}")
            print(f"  -> Full response hex: {' '.join(f'{b:02x}' for b in padded_response)}")

def handle_event(fd):
    event = v4l2_event()
    try:
        event_p = ctypes.pointer(event)
        fcntl.ioctl(fd, VIDIOC_DQEVENT, event_p)
        
        print(f"\nEvent received:")
        print(f"  Type: 0x{event.type:08x}")
        print(f"  Sequence: {event.sequence}")
        print(f"  Pending: {event.pending}")
        
        # Print first 16 bytes of event data
        print("  Event data (first 16 bytes):", end=" ")
        event_data = bytes(event.u.data)[:16]
        print(' '.join(f'{b:02x}' for b in event_data))
        
        if event.type == UVC_EVENT_SETUP:
            handle_setup_event(fd, bytes(event.u.data[0:8]))
        elif event.type == UVC_EVENT_STREAMON:
            print("Stream ON event received")
        elif event.type == UVC_EVENT_STREAMOFF:
            print("Stream OFF event received")
        elif event.type == UVC_EVENT_DATA:
            print("Data event received")
        elif event.type == UVC_EVENT_CONNECT:
            print("Connect event received")
        elif event.type == UVC_EVENT_DISCONNECT:
            print("Disconnect event received")
        elif event.type == 0:
            print("Warning: Received event with type 0")
            
    except Exception as e:
        print(f"Error handling event: {e}")
        print(f"Error details: {e!r}")
        print(f"Event structure size: {sizeof(event)}")
        # Print raw memory of the event structure to debug
        event_bytes = bytes(event)
        print("Raw event memory:")
        for i in range(0, sizeof(event), 16):
            hex_data = ' '.join(f'{b:02x}' for b in event_bytes[i:i+16])
            print(f"  {hex_data}")

def main():
    try:
        device_path = "/dev/video0"
        print(f"Opening {device_path}")
        fd = os.open(device_path, os.O_RDWR | os.O_NONBLOCK)
        
        # Subscribe to all valid events
        event_types = [
            UVC_EVENT_SETUP,     # 0x08000004 - Most important for handling control requests
            UVC_EVENT_DATA,      # 0x08000005 - For data stage of control requests
            UVC_EVENT_STREAMON,  # 0x08000002 - Stream control
            UVC_EVENT_STREAMOFF, # 0x08000003 - Stream control
            UVC_EVENT_CONNECT,   # 0x08000000 - Device connection
            UVC_EVENT_DISCONNECT # 0x08000001 - Device disconnection
        ]
        
        for event_type in event_types:
            subscribe_event(fd, event_type)

        print("\nDevice ready - waiting for events...")
        print("Structure sizes:")
        print(f"v4l2_event: {sizeof(v4l2_event)}")
        print(f"timeval: {sizeof(timeval)}")
        
        poll = select.poll()
        poll.register(fd, select.POLLPRI | select.POLLERR | select.POLLHUP)
        
        while True:
            events = poll.poll(1000)
            if events:
                for fd, event_mask in events:
                    print(f"\nPoll event received - mask: 0x{event_mask:04x}")
                    handle_event(fd)

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        if 'fd' in locals():
            os.close(fd)
            print("Device closed")

if __name__ == "__main__":
    main()
