#!/usr/bin/env python3
import fcntl
import struct
import os
import time
import select
import ctypes
from ctypes import Structure, c_uint32, c_uint8, c_long

# V4L2 and UVC constants
VIDIOC_SUBSCRIBE_EVENT = 0x4020565a
VIDIOC_DQEVENT = 0x8010565d
UVCIOC_SEND_RESPONSE = 0x40087544

# UVC event types
UVC_EVENT_SETUP = 0x08000004
UVC_EVENT_DATA = 0x08000005
UVC_EVENT_STREAMON = 0x08000002
UVC_EVENT_STREAMOFF = 0x08000003

# Define proper timeval structure
class timeval(Structure):
    _fields_ = [
        ('tv_sec', c_long),
        ('tv_usec', c_long)
    ]

# Define v4l2_event structure with correct memory layout
class v4l2_event(Structure):
    _fields_ = [
        ('type', c_uint32),
        ('u', c_uint8 * 64),  # Union of event data
        ('pending', c_uint32),
        ('sequence', c_uint32),
        ('timestamp', timeval),  # Changed to use timeval structure
        ('id', c_uint32),
        ('reserved', c_uint32 * 8)
    ]

def subscribe_event(fd, event_type):
    # Using ctypes for subscription structure too
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
    
    fcntl.ioctl(fd, VIDIOC_SUBSCRIBE_EVENT, sub)

def send_response(fd, data):
    try:
        fcntl.ioctl(fd, UVCIOC_SEND_RESPONSE, data)
    except Exception as e:
        print(f"Error sending response: {e}")

def handle_setup_event(fd, event):
    setup_data = bytes(event.u[0:8])
    bmRequestType, bRequest, wValue, wIndex, wLength = struct.unpack('<BBHHH', setup_data)
    
    print(f"Setup Request: bmRequestType=0x{bmRequestType:02x}, bRequest=0x{bRequest:02x}, "
          f"wValue=0x{wValue:04x}, wIndex=0x{wIndex:04x}, wLength=0x{wLength:04x}")

    response_data = None

    if bmRequestType == 0xA1:  # Class-specific GET requests
        if bRequest == 0x86:  # GET_INFO
            print("-> GET_INFO: Returning info about the control.")
            response_data = struct.pack('<B', 0x03)  # Support GET/SET
        elif bRequest == 0x82:  # GET_MIN
            print("-> GET_MIN: Returning minimum value.")
            response_data = struct.pack('<H', 0x0000)
        elif bRequest == 0x83:  # GET_MAX
            print("-> GET_MAX: Returning maximum value.")
            response_data = struct.pack('<H', 0x00FF)
        elif bRequest == 0x84:  # GET_RES
            print("-> GET_RES: Returning resolution step.")
            response_data = struct.pack('<H', 0x0001)
        elif bRequest == 0x87:  # GET_DEF
            print("-> GET_DEF: Returning default value.")
            response_data = struct.pack('<H', 0x007F)

    if response_data is not None:
        padded_response = response_data.ljust(124, b'\0')  # Ensure the response fits 124 bytes
        send_response(fd, padded_response)
    else:
        print("-> Unsupported or unhandled request.")

def handle_streaming(fd, stream_on):
    if stream_on:
        print("Stream ON: Starting video stream.")
        # TODO: Add logic for buffer allocation and streaming
    else:
        print("Stream OFF: Stopping video stream.")
        # TODO: Release buffers and stop the stream

def handle_event(fd):
    event = v4l2_event()
    try:
        # Pass by reference for ioctl
        fcntl.ioctl(fd, VIDIOC_DQEVENT, event)
        
        if event.type == UVC_EVENT_SETUP:
            handle_setup_event(fd, event)
        elif event.type == UVC_EVENT_STREAMON:
            handle_streaming(fd, stream_on=True)
        elif event.type == UVC_EVENT_STREAMOFF:
            handle_streaming(fd, stream_on=False)
        else:
            print(f"Unhandled event type: 0x{event.type:08x}")
    except Exception as e:
        print(f"Error dequeuing event: {e}")
        # Debug: Print structure sizes and memory layout
        print(f"Event structure size: {ctypes.sizeof(event)}")
        print(f"Event type: 0x{event.type:08x}")
        print(f"Event memory: {bytes(event)[:32].hex()}")

def main():
    try:
        device_path = "/dev/video0"
        print(f"Opening {device_path}")
        fd = os.open(device_path, os.O_RDWR | os.O_NONBLOCK)
        
        # Subscribe to events
        event_types = [UVC_EVENT_SETUP, UVC_EVENT_DATA, UVC_EVENT_STREAMON, UVC_EVENT_STREAMOFF]
        for event_type in event_types:
            try:
                subscribe_event(fd, event_type)
                print(f"Successfully subscribed to event 0x{event_type:08x}")
            except Exception as e:
                print(f"Failed to subscribe to event 0x{event_type:08x}: {e}")
                os.close(fd)
                return

        print("\nDevice ready - starting event loop")
        print("Will print event details when they arrive")
        
        poll = select.poll()
        poll.register(fd, select.POLLIN | select.POLLPRI)
        
        while True:
            events = poll.poll(1000)
            if events:
                for fd, event_mask in events:
                    print(f"\nReceived event with mask: 0x{event_mask:04x}")
                    if event_mask & select.POLLIN:
                        print("POLLIN event")
                    if event_mask & select.POLLPRI:
                        print("POLLPRI event")
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