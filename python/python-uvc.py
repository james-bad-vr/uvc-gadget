#!/usr/bin/env python3
import fcntl
import struct
import os
import time
import select
import ctypes

# V4L2 and UVC constants
VIDIOC_SUBSCRIBE_EVENT = 0x4020565a
VIDIOC_DQEVENT = 0x8010565d
UVCIOC_SEND_RESPONSE = 0x40087544

# UVC event types
UVC_EVENT_SETUP = 0x08000004
UVC_EVENT_DATA = 0x08000005
UVC_EVENT_STREAMON = 0x08000002
UVC_EVENT_STREAMOFF = 0x08000003

# Define v4l2_event structure
class v4l2_event(ctypes.Structure):
    _fields_ = [
        ('type', ctypes.c_uint32),
        ('u', ctypes.c_uint8 * 64),  # Union of event data
        ('pending', ctypes.c_uint32),
        ('sequence', ctypes.c_uint32),
        ('timestamp', ctypes.c_uint64),
        ('id', ctypes.c_uint32),
        ('reserved', ctypes.c_uint32 * 8)
    ]

def subscribe_event(fd, event_type):
    data = struct.pack('IIIi16s', 
        event_type,  # type
        0,          # id
        0,          # flags
        0,          # reserved[0]
        b'\0' * 16  # remaining reserved bytes
    )
    fcntl.ioctl(fd, VIDIOC_SUBSCRIBE_EVENT, data)

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

    # Handle PROBE and COMMIT control requests
    if bmRequestType == 0x21:  # Host-to-device, Interface
        if bRequest == 0x01:  # SET_CUR
            print("-> Host is setting streaming parameters (PROBE/COMMIT).")
            response = struct.pack('i124s', 0, b'\0' * 124)  # Example response
            send_response(fd, response)
        elif bRequest == 0x81:  # GET_CUR
            print("-> Host is requesting current streaming parameters.")
            response = struct.pack('i124s', 0, b'\x00' * 124)  # Current settings
            send_response(fd, response)
    else:
        print("-> Unknown or unsupported request.")

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
        fcntl.ioctl(fd, VIDIOC_DQEVENT, event)
        if event.type == UVC_EVENT_SETUP:
            handle_setup_event(fd, event)
        elif event.type == UVC_EVENT_STREAMON:
            handle_streaming(fd, stream_on=True)
        elif event.type == UVC_EVENT_STREAMOFF:
            handle_streaming(fd, stream_on=False)
        else:
            print(f"Unhandled event type: {event.type}")
    except Exception as e:
        print(f"Error dequeuing event: {e}")

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
        print("Will print '.' when polling and full details when events arrive")
        
        poll = select.poll()
        poll.register(fd, select.POLLIN | select.POLLPRI)
        
        while True:
            events = poll.poll(1000)
            if events:
                print("\nReceived poll event!")
                for fd, event_mask in events:
                    print(f"Event mask: 0x{event_mask:04x}")
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