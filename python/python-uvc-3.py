#!/usr/bin/env python3
import fcntl
import struct
import os
import time
import select
import ctypes
from ctypes import Structure, Union, c_uint32, c_uint8, c_long, c_int32, c_uint16

# IOCTL codes
VIDIOC_SUBSCRIBE_EVENT = 0x4020565a
VIDIOC_DQEVENT = 0x80805659
UVCIOC_SEND_RESPONSE = 0x40087544

# UVC event types (from g_uvc.h)
V4L2_EVENT_PRIVATE_START = 0x08000000
UVC_EVENT_CONNECT    = V4L2_EVENT_PRIVATE_START + 0
UVC_EVENT_DISCONNECT = V4L2_EVENT_PRIVATE_START + 1
UVC_EVENT_STREAMON   = V4L2_EVENT_PRIVATE_START + 2
UVC_EVENT_STREAMOFF  = V4L2_EVENT_PRIVATE_START + 3
UVC_EVENT_SETUP      = V4L2_EVENT_PRIVATE_START + 4
UVC_EVENT_DATA       = V4L2_EVENT_PRIVATE_START + 5

class usb_ctrlrequest(Structure):
    _fields_ = [
        ('bRequestType', c_uint8),
        ('bRequest', c_uint8),
        ('wValue', c_uint16),
        ('wIndex', c_uint16),
        ('wLength', c_uint16),
    ]

class uvc_request_data(Structure):
    _fields_ = [
        ('length', c_int32),
        ('data', c_uint8 * 60),
    ]

class uvc_event(Union):
    _fields_ = [
        ('speed', c_uint32),       # enum usb_device_speed
        ('req', usb_ctrlrequest),
        ('data', uvc_request_data),
    ]

class timeval(Structure):
    _fields_ = [
        ('tv_sec', c_long),
        ('tv_usec', c_long)
    ]

class v4l2_event(Structure):
    _fields_ = [
        ('type', c_uint32),
        ('u', uvc_event),
        ('pending', c_uint32),
        ('sequence', c_uint32),
        ('timestamp', timeval),
        ('id', c_uint32),
        ('reserved', c_uint32 * 8)
    ]

class v4l2_event_subscription(Structure):
    _fields_ = [
        ('type', c_uint32),
        ('id', c_uint32),
        ('flags', c_uint32),
        ('reserved', c_uint32 * 5)
    ]

def handle_setup_event(fd, event):
    req = event.u.req
    print(f"Setup Request:")
    print(f"  bmRequestType: 0x{req.bRequestType:02x}")
    print(f"  bRequest: 0x{req.bRequest:02x}")
    print(f"  wValue: 0x{req.wValue:04x}")
    print(f"  wIndex: 0x{req.wIndex:04x}")
    print(f"  wLength: {req.wLength}")

    response = uvc_request_data()
    response.length = -1  # Default to no response

    if req.bRequestType == 0xA1:  # Class-specific GET request
        if req.bRequest == 0x86:   # GET_INFO
            print("  -> GET_INFO request")
            response.data[0] = 0x03  # GET/SET supported
            response.length = 1
        elif req.bRequest == 0x87:  # GET_DEF
            print("  -> GET_DEF request")
            struct.pack_into('<H', response.data, 0, 0x007F)
            response.length = 2
        elif req.bRequest == 0x82:  # GET_MIN
            print("  -> GET_MIN request")
            struct.pack_into('<H', response.data, 0, 0x0000)
            response.length = 2
        elif req.bRequest == 0x83:  # GET_MAX
            print("  -> GET_MAX request")
            struct.pack_into('<H', response.data, 0, 0x00FF)
            response.length = 2
        elif req.bRequest == 0x84:  # GET_RES
            print("  -> GET_RES request")
            struct.pack_into('<H', response.data, 0, 0x0001)
            response.length = 2

    if response.length > 0:
        try:
            fcntl.ioctl(fd, UVCIOC_SEND_RESPONSE, response)
            print("  -> Response sent successfully")
            print(f"  -> Response length: {response.length}")
            print(f"  -> Response data: {' '.join(f'{b:02x}' for b in response.data[:response.length])}")
        except Exception as e:
            print(f"  -> Failed to send response: {e}")

def subscribe_event(fd, event_type):
    sub = v4l2_event_subscription()
    sub.type = event_type
    sub.id = 0
    sub.flags = 0
    
    try:
        fcntl.ioctl(fd, VIDIOC_SUBSCRIBE_EVENT, sub)
        print(f"Subscribed to event 0x{event_type:08x}")
    except Exception as e:
        print(f"Failed to subscribe to event 0x{event_type:08x}: {e}")
        raise

def handle_event(fd):
    event = v4l2_event()
    try:
        fcntl.ioctl(fd, VIDIOC_DQEVENT, event)
        
        print(f"\nEvent received:")
        print(f"  Type: 0x{event.type:08x}")
        print(f"  Sequence: {event.sequence}")
        print(f"  Pending: {event.pending}")
        
        if event.type == UVC_EVENT_SETUP:
            handle_setup_event(fd, event)
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
            print("Event memory:")
            event_bytes = bytes(event)
            for i in range(0, len(event_bytes), 16):
                print(f"  {' '.join(f'{b:02x}' for b in event_bytes[i:i+16])}")
            
    except Exception as e:
        print(f"Error handling event: {e}")
        print(f"Event structure size: {sizeof(event)}")
        print("Event memory:")
        event_bytes = bytes(event)
        for i in range(0, len(event_bytes), 16):
            print(f"  {' '.join(f'{b:02x}' for b in event_bytes[i:i+16])}")

def main():
    try:
        device_path = "/dev/video0"
        print(f"Opening {device_path}")
        fd = os.open(device_path, os.O_RDWR | os.O_NONBLOCK)
        
        # Subscribe to all valid events
        event_types = [
            UVC_EVENT_SETUP,
            UVC_EVENT_DATA,
            UVC_EVENT_STREAMON,
            UVC_EVENT_STREAMOFF,
            UVC_EVENT_CONNECT,
            UVC_EVENT_DISCONNECT
        ]
        
        for event_type in event_types:
            subscribe_event(fd, event_type)

        print("\nDevice ready - waiting for events...")
        print(f"Structure sizes:")
        print(f"  v4l2_event: {sizeof(v4l2_event)}")
        print(f"  uvc_event: {sizeof(uvc_event)}")
        print(f"  uvc_request_data: {sizeof(uvc_request_data)}")
        print(f"  usb_ctrlrequest: {sizeof(usb_ctrlrequest)}")
        
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
