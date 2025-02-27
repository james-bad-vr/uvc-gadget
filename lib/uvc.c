/* SPDX-License-Identifier: LGPL-2.1-or-later */
/*
 * UVC protocol handling
 *
 * Copyright (C) 2010-2018 Laurent Pinchart
 *
 * Contact: Laurent Pinchart <laurent.pinchart@ideasonboard.com>
 */

#include <errno.h>
#include <limits.h>
#include <linux/usb/ch9.h>
#include <linux/usb/g_uvc.h>
#include <linux/usb/video.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>

#include "configfs.h"
#include "events.h"
#include "stream.h"
#include "tools.h"
#include "uvc.h"
#include "v4l2.h"

struct uvc_device
{
	struct v4l2_device *vdev;

	struct uvc_stream *stream;
	struct uvc_function_config *fc;

	struct uvc_streaming_control probe;
	struct uvc_streaming_control commit;

	int control;

	unsigned int fcc;
	unsigned int width;
	unsigned int height;
};

static const char *uvc_request_names[] = {
	[UVC_RC_UNDEFINED] = "UNDEFINED",
	[UVC_SET_CUR] = "SET_CUR",
	[UVC_GET_CUR] = "GET_CUR",
	[UVC_GET_MIN] = "GET_MIN",
	[UVC_GET_MAX] = "GET_MAX",
	[UVC_GET_RES] = "GET_RES",
	[UVC_GET_LEN] = "GET_LEN",
	[UVC_GET_INFO] = "GET_INFO",
	[UVC_GET_DEF] = "GET_DEF",
};

static const char *uvc_request_name(uint8_t req)
{
    if (req < ARRAY_SIZE(uvc_request_names))
        return uvc_request_names[req];
    else
        return "UNKNOWN";
}

static const char *uvc_pu_control_names[] = {
	[UVC_PU_CONTROL_UNDEFINED] = "UNDEFINED",
	[UVC_PU_BACKLIGHT_COMPENSATION_CONTROL] = "BACKLIGHT_COMPENSATION",
	[UVC_PU_BRIGHTNESS_CONTROL] = "BRIGHTNESS",
	[UVC_PU_CONTRAST_CONTROL] = "CONTRAST",
	[UVC_PU_GAIN_CONTROL] = "GAIN",
	[UVC_PU_POWER_LINE_FREQUENCY_CONTROL] = "POWER_LINE_FREQUENCY",
	[UVC_PU_HUE_CONTROL] = "HUE",
	[UVC_PU_SATURATION_CONTROL] = "SATURATION",
	[UVC_PU_SHARPNESS_CONTROL] = "SHARPNESS",
	[UVC_PU_GAMMA_CONTROL] = "GAMMA",
	[UVC_PU_WHITE_BALANCE_TEMPERATURE_CONTROL] = "WHITE_BALANCE_TEMPERATURE",
	[UVC_PU_WHITE_BALANCE_TEMPERATURE_AUTO_CONTROL] = "WHITE_BALANCE_TEMPERATURE_AUTO",
	[UVC_PU_WHITE_BALANCE_COMPONENT_CONTROL] = "WHITE_BALANCE_COMPONENT",
	[UVC_PU_WHITE_BALANCE_COMPONENT_AUTO_CONTROL] = "WHITE_BALANCE_COMPONENT_AUTO",
	[UVC_PU_DIGITAL_MULTIPLIER_CONTROL] = "DIGITAL_MULTIPLIER",
	[UVC_PU_DIGITAL_MULTIPLIER_LIMIT_CONTROL] = "DIGITAL_MULTIPLIER_LIMIT",
	[UVC_PU_HUE_AUTO_CONTROL] = "HUE_AUTO",
	[UVC_PU_ANALOG_VIDEO_STANDARD_CONTROL] = "ANALOG_VIDEO_STANDARD",
	[UVC_PU_ANALOG_LOCK_STATUS_CONTROL] = "ANALOG_LOCK_STATUS",
};

static const char *pu_control_name(uint8_t cs)
{
    if (cs < ARRAY_SIZE(uvc_pu_control_names))
        return uvc_pu_control_names[cs];
    else
        return "UNKNOWN";
}

struct uvc_device *uvc_open(const char *devname, struct uvc_stream *stream)
{
	struct uvc_device *dev;
	
	printf("uvc_open\n");

	dev = malloc(sizeof *dev);
	if (dev == NULL)
		return NULL;

	memset(dev, 0, sizeof *dev);
	dev->stream = stream;

	dev->vdev = v4l2_open(devname);
	
	if (dev->vdev == NULL)
	{
		free(dev);
		return NULL;
	}

	return dev;
}

void uvc_close(struct uvc_device *dev)
{
	printf("uvc_close\n");
	
	v4l2_close(dev->vdev);
	dev->vdev = NULL;

	free(dev);
}

/* ---------------------------------------------------------------------------
 * Request processing
 */

static void
uvc_fill_streaming_control(struct uvc_device *dev,
			   struct uvc_streaming_control *ctrl,
			   int iformat, int iframe, unsigned int ival)
{
	const struct uvc_function_config_format *format;
	const struct uvc_function_config_frame *frame;
	unsigned int i;
	
    printf("uvc_fill_streaming_control\n");
	
	/*
	 * Restrict the iformat, iframe and ival to valid values. Negative
	 * values for iformat or iframe will result in the maximum valid value
	 * being selected.
	 */
    iformat = clamp((unsigned int)iformat, 1U, dev->fc->streaming.num_formats);
	format = &dev->fc->streaming.formats[iformat-1];

	iframe = clamp((unsigned int)iframe, 1U, format->num_frames);
	frame = &format->frames[iframe-1];

	for (i = 0; i < frame->num_intervals; ++i)
	{
		if (ival <= frame->intervals[i])
		{
			ival = frame->intervals[i];
			break;
		}
	}

	if (i == frame->num_intervals)
		ival = frame->intervals[frame->num_intervals-1];

	memset(ctrl, 0, sizeof *ctrl);

	ctrl->bmHint = 1;
	ctrl->bFormatIndex = iformat;
	ctrl->bFrameIndex = iframe ;
	ctrl->dwFrameInterval = ival;

	/*
	 * The maximum size in bytes for a single frame depends on the format.
	 * This switch will need extending for any new formats that are added
	 * to ensure the buffer size calculations are done correctly.
	 */
	switch (format->fcc)
	{
		case V4L2_PIX_FMT_YUYV:
		case V4L2_PIX_FMT_MJPEG:
			ctrl->dwMaxVideoFrameSize = frame->width * frame->height * 2;
			break;
	}

	ctrl->dwMaxPayloadTransferSize = dev->fc->streaming.ep.wMaxPacketSize;
	ctrl->bmFramingInfo = 3;
	ctrl->bPreferedVersion = 1;
	ctrl->bMaxVersion = 1;
}

static void
uvc_events_process_standard(struct uvc_device *dev,
			    const struct usb_ctrlrequest *ctrl,
			    struct uvc_request_data *resp)
{
	printf("standard request\n");
	(void)dev;
	(void)ctrl;
	(void)resp;
}

static void
uvc_events_process_control(struct uvc_device *dev, uint8_t req, uint8_t cs, uint8_t len,
			   struct uvc_request_data *resp)
{
	printf("control request (req %s cs %s)\n", uvc_request_name(req), pu_control_name(cs));
	(void)dev;

	/*
	 * Responding to controls is not currently implemented. As an interim
	 * measure respond to say that both get and set operations are permitted.
	 */
	resp->data[0] = 0x03;
	resp->length = len;
}

static void
uvc_events_process_streaming(struct uvc_device *dev, uint8_t req, uint8_t cs,
			     struct uvc_request_data *resp)
{
	struct uvc_streaming_control *ctrl;

	printf("\n=== UVC Streaming Request ===\n");

	printf("streaming request (req %s cs %02x)\n", uvc_request_name(req), cs);

	printf("Control Selector: %s (0x%02x)\n", 
           cs == UVC_VS_PROBE_CONTROL ? "PROBE" : 
           cs == UVC_VS_COMMIT_CONTROL ? "COMMIT" : "UNKNOWN",
           cs);

	 if (cs != UVC_VS_PROBE_CONTROL && cs != UVC_VS_COMMIT_CONTROL) {
        printf("Invalid control selector, ignoring request\n");
        return;
    }

	ctrl = (struct uvc_streaming_control *)&resp->data;
	resp->length = sizeof *ctrl;

	printf("Initial response length: %zu bytes\n", resp->length);

	switch (req) {
	case UVC_SET_CUR:
		printf("SET_CUR Request\n");
        printf("Setting control to: %s\n", 
               cs == UVC_VS_PROBE_CONTROL ? "PROBE" : "COMMIT");
		dev->control = cs;
		resp->length = 34;
		break;

	case UVC_GET_CUR:
		printf("GET_CUR Request for %s\n", 
               cs == UVC_VS_PROBE_CONTROL ? "PROBE" : "COMMIT");
		if (cs == UVC_VS_PROBE_CONTROL)
		{
			printf("Copying PROBE control data:\n");
            printf("Before copy - First 4 bytes: %02x %02x %02x %02x\n",
                   resp->data[0], resp->data[1], resp->data[2], resp->data[3]);
			memcpy(ctrl, &dev->probe, sizeof *ctrl);
			printf("After copy - First 4 bytes: %02x %02x %02x %02x\n",
                   resp->data[0], resp->data[1], resp->data[2], resp->data[3]);
		}	
		else
		{
			printf("Copying COMMIT control data:\n");
            printf("Before copy - First 4 bytes: %02x %02x %02x %02x\n",
                   resp->data[0], resp->data[1], resp->data[2], resp->data[3]);
            memcpy(ctrl, &dev->commit, sizeof *ctrl);
            printf("After copy - First 4 bytes: %02x %02x %02x %02x\n",
                   resp->data[0], resp->data[1], resp->data[2], resp->data[3]);
		}
		printf("Control data: bmHint=%04x, format=%d, frame=%d\n",
			ctrl->bmHint, ctrl->bFormatIndex, ctrl->bFrameIndex);
		printf("Frame interval=%d, keyframe=%d, pframe=%d\n",
			ctrl->dwFrameInterval, ctrl->wKeyFrameRate, ctrl->wPFrameRate);
		printf("Comp quality=%d, window=%d\n",
			ctrl->wCompQuality, ctrl->wCompWindowSize);
		break;

	case UVC_GET_MIN:
	case UVC_GET_MAX:
	case UVC_GET_DEF:
		if (req == UVC_GET_MAX)
			uvc_fill_streaming_control(dev, ctrl, -1, -1, UINT_MAX);
		else
			uvc_fill_streaming_control(dev, ctrl, 1, 1, 0);
		break;

	case UVC_GET_RES:
		memset(ctrl, 0, sizeof *ctrl);
		break;

	case UVC_GET_LEN:
		resp->data[0] = 0x00;
		resp->data[1] = 0x22;
		resp->length = 2;
		break;

	case UVC_GET_INFO:
		resp->data[0] = 0x03;
		resp->length = 1;
		break;
	}
}

static void
uvc_events_process_class(struct uvc_device *dev,
			 const struct usb_ctrlrequest *ctrl,
			 struct uvc_request_data *resp)
{
	unsigned int interface = ctrl->wIndex & 0xff;
	
	printf("uvc_events_process_class\n");

	if ((ctrl->bRequestType & USB_RECIP_MASK) != USB_RECIP_INTERFACE)
		return;

	if (interface == dev->fc->control.intf.bInterfaceNumber)
		uvc_events_process_control(dev, ctrl->bRequest, ctrl->wValue >> 8, ctrl->wLength, resp);
	else if (interface == dev->fc->streaming.intf.bInterfaceNumber)
		uvc_events_process_streaming(dev, ctrl->bRequest, ctrl->wValue >> 8, resp);
}

static void
uvc_events_process_setup(struct uvc_device *dev,
			 const struct usb_ctrlrequest *ctrl,
			 struct uvc_request_data *resp)
{
	dev->control = 0;

	printf("bRequestType %02x bRequest %02x wValue %04x wIndex %04x "
		"wLength %04x\n", ctrl->bRequestType, ctrl->bRequest,
		ctrl->wValue, ctrl->wIndex, ctrl->wLength);

	switch (ctrl->bRequestType & USB_TYPE_MASK)
	{
		case USB_TYPE_STANDARD:
			uvc_events_process_standard(dev, ctrl, resp);
			break;

		case USB_TYPE_CLASS:
			uvc_events_process_class(dev, ctrl, resp);
			break;

		default:
			break;
	}
}

static void
uvc_events_process_data(struct uvc_device *dev,
			const struct uvc_request_data *data)
{
	const struct uvc_streaming_control *ctrl =
		(const struct uvc_streaming_control *)&data->data;
	struct uvc_streaming_control *target;
	
	switch (dev->control)
	{
		case UVC_VS_PROBE_CONTROL:
			printf("setting probe control, length = %d\n", data->length);
			target = &dev->probe;
			break;

		case UVC_VS_COMMIT_CONTROL:
			printf("setting commit control, length = %d\n", data->length);
			target = &dev->commit;
			break;

		default:
			printf("setting unknown control, length = %d\n", data->length);
			return;
	}

	uvc_fill_streaming_control(dev, target, ctrl->bFormatIndex,
				   ctrl->bFrameIndex, ctrl->dwFrameInterval);

	if (dev->control == UVC_VS_COMMIT_CONTROL)
	{
		const struct uvc_function_config_format *format;
		const struct uvc_function_config_frame *frame;
		struct v4l2_pix_format pixfmt;
		unsigned int fps;

		format = &dev->fc->streaming.formats[target->bFormatIndex-1];
		frame = &format->frames[target->bFrameIndex-1];

		dev->fcc = format->fcc;
		dev->width = frame->width;
		dev->height = frame->height;

		memset(&pixfmt, 0, sizeof pixfmt);
		pixfmt.width = frame->width;
		pixfmt.height = frame->height;
		pixfmt.pixelformat = format->fcc;
		pixfmt.field = V4L2_FIELD_NONE;
		
		if (format->fcc == V4L2_PIX_FMT_MJPEG)
			pixfmt.sizeimage = target->dwMaxVideoFrameSize;

		uvc_stream_set_format(dev->stream, &pixfmt);

		/* fps is guaranteed to be non-zero and thus valid. */
		fps = 1.0 / (target->dwFrameInterval / 10000000.0);
		uvc_stream_set_frame_rate(dev->stream, fps);
	}
}

static void uvc_events_process(void *d)
{
  	struct uvc_device *dev = d;
    struct v4l2_event v4l2_event;
    const struct uvc_event *uvc_event = (void *)&v4l2_event.u.data;
    struct uvc_request_data resp;
    int ret;

    // Print structure sizes
    printf("\nStructure sizes:\n");
    printf("v4l2_event size: %zu bytes\n", sizeof(struct v4l2_event));
    printf("v4l2_event.u.data size: %zu bytes\n", sizeof(v4l2_event.u.data));

    printf("#### Calling ioctl: VIDIOC_DQEVENT\n");
    ret = ioctl(dev->vdev->fd, VIDIOC_DQEVENT, &v4l2_event);
    
    if (ret < 0) {
        printf("VIDIOC_DQEVENT failed: %s (%d)\n", strerror(errno), errno);
        return;
    } else {
        printf("VIDIOC_DQEVENT succeeded\n");
    }

    // Print event details
    printf("\nEvent details:\n");
    printf("event.type: 0x%08x\n", v4l2_event.type);
    printf("event.pending: %u\n", v4l2_event.pending);
    printf("event.sequence: %u\n", v4l2_event.sequence);
    printf("event.id: %u\n", v4l2_event.id);

    // Print first few bytes of data in hex
    printf("event.u.data (first 16 bytes): ");
    for (int i = 0; i < 16; i++) {
        printf("%02x ", v4l2_event.u.data[i]);
    }
    printf("\n");

    memset(&resp, 0, sizeof resp);
    resp.length = -EL2HLT;

	switch (v4l2_event.type)
	{
		case UVC_EVENT_CONNECT:
		case UVC_EVENT_DISCONNECT:
			printf("uvc_events_process: UVC_EVENT_CONNECT or UVC_EVENT_DISCONNECT\n");
			return;

		case UVC_EVENT_SETUP:
			printf("uvc_events_process: UVC_EVENT_SETUP\n");
			uvc_events_process_setup(dev, &uvc_event->req, &resp);
			break;

		case UVC_EVENT_DATA:
			printf("uvc_events_process: UVC_EVENT_DATA\n");
			uvc_events_process_data(dev, &uvc_event->data);
			return;

		case UVC_EVENT_STREAMON:
			printf("uvc_events_process: UVC_EVENT_STREAMON\n");
			uvc_stream_enable(dev->stream, 1);
			return;

		case UVC_EVENT_STREAMOFF:
			printf("uvc_events_process: UVC_EVENT_STREAMOFF\n");
			uvc_stream_enable(dev->stream, 0);
			return;
	}

	  // Log the response before sending
    printf("\nResponse being sent:\n");
    printf("resp.length: %d\n", resp.length);
    printf("resp.data (first 16 bytes): ");
    for (int i = 0; i < 16 && i < resp.length; i++) {
        printf("%02x ", (unsigned char)resp.data[i]);
    }
    printf("\n");


    printf("#### Calling ioctl: UVCIOC_SEND_RESPONSE\n");
	ret = ioctl(dev->vdev->fd, UVCIOC_SEND_RESPONSE, &resp);
	
	if (ret < 0)
	{
		printf("UVCIOC_SEND_RESPONSE failed: %s (%d)\n",
		       strerror(errno), errno);
	} else {
        printf("UVCIOC_SEND_RESPONSE succeeded\n");
    }
}


/* ---------------------------------------------------------------------------
 * Initialization and setup
 */

void uvc_events_init(struct uvc_device *dev, struct events *events)
{
    struct v4l2_event_subscription sub;
    int ret;
    
    printf("uvc_events_init\n");
    printf("VIDIOC_SUBSCRIBE_EVENT = 0x%08x\n", VIDIOC_SUBSCRIBE_EVENT);

    /* Default to the minimum values. */
    uvc_fill_streaming_control(dev, &dev->probe, 1, 1, 0);
    uvc_fill_streaming_control(dev, &dev->commit, 1, 1, 0);

    printf("Size of v4l2_event_subscription struct: %zu bytes\n", sizeof(struct v4l2_event_subscription));
    
    memset(&sub, 0, sizeof sub);

    sub.type = UVC_EVENT_SETUP;
    printf("UVC_EVENT_SETUP = %d (0x%08x)\n", sub.type, sub.type);
    printf("Subscribing to SETUP - sub struct: type=%u, id=%u, flags=%u\n", sub.type, sub.id, sub.flags);
    
    printf("#### Calling ioctl: VIDIOC_SUBSCRIBE_EVENT for UVC_EVENT_SETUP\n");
    ret = ioctl(dev->vdev->fd, VIDIOC_SUBSCRIBE_EVENT, &sub);
    if (ret < 0)
        printf("VIDIOC_SUBSCRIBE_EVENT (UVC_EVENT_SETUP) failed: %s (%d)\n", strerror(errno), errno);
    else
        printf("VIDIOC_SUBSCRIBE_EVENT (UVC_EVENT_SETUP) succeeded\n");

    sub.type = UVC_EVENT_DATA;
    printf("UVC_EVENT_DATA = %d (0x%08x)\n", sub.type, sub.type);
    printf("Subscribing to DATA - sub struct: type=%u, id=%u, flags=%u\n", sub.type, sub.id, sub.flags);

    printf("#### Calling ioctl: VIDIOC_SUBSCRIBE_EVENT for UVC_EVENT_DATA\n");
    ret = ioctl(dev->vdev->fd, VIDIOC_SUBSCRIBE_EVENT, &sub);
    if (ret < 0)
        printf("VIDIOC_SUBSCRIBE_EVENT (UVC_EVENT_DATA) failed: %s (%d)\n", strerror(errno), errno);
    else
        printf("VIDIOC_SUBSCRIBE_EVENT (UVC_EVENT_DATA) succeeded\n");

    sub.type = UVC_EVENT_STREAMON;
    printf("UVC_EVENT_STREAMON = %d (0x%08x)\n", sub.type, sub.type);
    printf("Subscribing to STREAMON - sub struct: type=%u, id=%u, flags=%u\n", sub.type, sub.id, sub.flags);

    printf("#### Calling ioctl: VIDIOC_SUBSCRIBE_EVENT for UVC_EVENT_STREAMON\n");
    ret = ioctl(dev->vdev->fd, VIDIOC_SUBSCRIBE_EVENT, &sub);
    if (ret < 0)
        printf("VIDIOC_SUBSCRIBE_EVENT (UVC_EVENT_STREAMON) failed: %s (%d)\n", strerror(errno), errno);
    else
        printf("VIDIOC_SUBSCRIBE_EVENT (UVC_EVENT_STREAMON) succeeded\n");

    sub.type = UVC_EVENT_STREAMOFF;
    printf("UVC_EVENT_STREAMOFF = %d (0x%08x)\n", sub.type, sub.type);
    printf("Subscribing to STREAMOFF - sub struct: type=%u, id=%u, flags=%u\n", sub.type, sub.id, sub.flags);

    printf("#### Calling ioctl: VIDIOC_SUBSCRIBE_EVENT for UVC_EVENT_STREAMOFF\n");
    ret = ioctl(dev->vdev->fd, VIDIOC_SUBSCRIBE_EVENT, &sub);
    if (ret < 0)
        printf("VIDIOC_SUBSCRIBE_EVENT (UVC_EVENT_STREAMOFF) failed: %s (%d)\n", strerror(errno), errno);
    else
        printf("VIDIOC_SUBSCRIBE_EVENT (UVC_EVENT_STREAMOFF) succeeded\n");

    events_watch_fd(events, dev->vdev->fd, EVENT_EXCEPTION, uvc_events_process, dev);
}


void uvc_set_config(struct uvc_device *dev, struct uvc_function_config *fc)
{
	dev->fc = fc;
}

int uvc_set_format(struct uvc_device *dev, struct v4l2_pix_format *format)
{
	printf("uvc_set_format\n");
	
	return v4l2_set_format(dev->vdev, format);
}

struct v4l2_device *uvc_v4l2_device(struct uvc_device *dev)
{
	/*
	 * TODO: The V4L2 device shouldn't be exposed. We should replace this
	 * with an abstract video sink class when one will be avaiilable.
	 */
	return dev->vdev;
}
