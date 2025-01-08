#!/usr/bin/env python3
import fcntl
import struct
import os
import time
import select

# V4L2 and UVC constants
VIDIOC_SUBSCRIBE_EVENT = 0x4020565a
VIDIOC_DQEVENT = 0x8010565d
UVCIOC_SEND_RESPONSE = 0x40087544

# UVC event types
UVC_EVENT_SETUP = 0x08000004
UVC_EVENT_DATA = 0x08000005
UVC_EVENT_STREAMON = 0x08000002
UVC_EVENT_STREAMOFF = 0x08000003

# Stream state
streaming = False

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

def handle_setup_event(fd, event_data):
    setup_data = event_data[4:12]  # 8 bytes of setup data
    bmRequestType, bRequest, wValue, wIndex, wLength = struct.unpack('<BBHHHH', setup_data)
    
    print(f"Setup Request: bmRequestType=0x{bmRequestType:02x} bRequest=0x{bRequest:02x} "
          f"wValue=0x{wValue:04x} wIndex=0x{wIndex:04x} wLength=0x{wLength:04x}")

    response_data = struct.pack('i124s', 0, b'\0' * 124)  # 128 bytes total
    send_response(fd, response_data)

def handle_event(fd):
    global streaming
    event_buf = bytearray(96)
    
    try:
        fcntl.ioctl(fd, VIDIOC_DQEVENT, event_buf)
        event_type = struct.unpack('I', event_buf[0:4])[0]
        
        if event_type == UVC_EVENT_SETUP:
            handle_setup_event(fd, event_buf)
        elif event_type == UVC_EVENT_DATA:
            data = event_buf[4:8]  # First 4 bytes after event type
            print(f"Data event received: {data.hex()}")
        elif event_type == UVC_EVENT_STREAMON:
            streaming = True
            print("\n=== Stream ON requested by host (e.g., OBS Studio) ===")
            print("Host is requesting to start video streaming")
            print("This typically happens when you select the UVC device in your application")
        elif event_type == UVC_EVENT_STREAMOFF:
            streaming = False
            print("\n=== Stream OFF requested by host ===")
            print("Host has stopped video streaming")
            print("This typically happens when you close the video preview or select a different device")
    except Exception as e:
        if hasattr(e, 'errno') and e.errno == 11:  # EAGAIN
            pass
        else:
            print(f"Error handling event: {e}")

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

        print("\nDevice ready - Waiting for events...")
        print("Open OBS Studio or another application and select the UVC device")
        
        poll = select.poll()
        poll.register(fd, select.POLLIN | select.POLLPRI)
        
        while True:
            events = poll.poll(1000)  # 1 second timeout
            for fd, event in events:
                handle_event(fd)
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nExiting...")
        if streaming:
            print("Note: Stream was still active when exiting")
    finally:
        if 'fd' in locals():
            os.close(fd)
            print("Closed device")

if __name__ == "__main__":
    main()