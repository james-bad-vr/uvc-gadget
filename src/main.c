/* SPDX-License-Identifier: GPL-2.0-or-later */
/*
 * UVC gadget test application
 *
 * Copyright (C) 2010-2018 Laurent Pinchart
 *
 * Contact: Laurent Pinchart <laurent.pinchart@ideasonboard.com>
 */

#include <signal.h>
#include <stdio.h>
#include <unistd.h>

#include "config.h"
#include "configfs.h"
#include "events.h"
#include "stream.h"
#include "test-source.h"

static void usage(const char *argv0)
{
	fprintf(stderr, "Usage: %s [options] <uvc device>\n", argv0);
	fprintf(stderr, "Available options are\n");
	fprintf(stderr, " -h		Print this help screen and exit\n");
	fprintf(stderr, "\n");
	fprintf(stderr, " <uvc device>	UVC device instance specifier\n");
	fprintf(stderr, "\n");

	fprintf(stderr, "  For ConfigFS devices the <uvc device> parameter can take the form of a shortened\n");
	fprintf(stderr, "  function specifier such as: 'uvc.0', or if multiple gadgets are configured, the\n");
	fprintf(stderr, "  gadget name should be included to prevent ambiguity: 'g1/functions/uvc.0'.\n");
	fprintf(stderr, "\n");
}

/* Necessary for and only used by signal handler. */
static struct events *sigint_events;

static void sigint_handler(int signal __attribute__((unused)))
{
	/* Stop the main loop when the user presses CTRL-C */
	events_stop(sigint_events);
}

int main(int argc, char *argv[])
{
	char *function = NULL;
	struct uvc_function_config *fc;
	struct uvc_stream *stream = NULL;
	struct video_source *src = NULL;
	struct events events;
	int ret = 0;
	int opt;

	while ((opt = getopt(argc, argv, "h")) != -1) {
		switch (opt) {
		case 'h':
			usage(argv[0]);
			return 0;
		default:
			fprintf(stderr, "Invalid option '-%c'\n", opt);
			usage(argv[0]);
			return 1;
		}
	}

	if (argv[optind] != NULL)
		function = argv[optind];
	printf("***** v1.1 *****\n");
	printf("minimal version\n");
	printf("configfs_parse_uvc_function\n");
	fc = configfs_parse_uvc_function(function);
	if (!fc) {
		printf("Failed to identify function configuration\n");
		return 1;
	}

	/*
	 * Create the events handler. Register a signal handler for SIGINT,
	 * received when the user presses CTRL-C. This will allow the main loop
	 * to be interrupted, and resources to be freed cleanly.
	 */
	printf("events_init\n");
	events_init(&events);

	sigint_events = &events;
	signal(SIGINT, sigint_handler);

	/* Create and initialize the test video source */
	src = test_video_source_create();
	if (src == NULL) {
		ret = 1;
		goto done;
	}

	/* Create and initialise the stream. */
	printf("uvc_stream_new\n");
	stream = uvc_stream_new(fc->video);
	if (stream == NULL) {
		ret = 1;
		goto done;
	}

	printf("uvc_stream_set_event_handler\n");
	uvc_stream_set_event_handler(stream, &events);
	
	printf("uvc_stream_set_video_source\n");
	uvc_stream_set_video_source(stream, src);
	
	printf("uvc_stream_init_uvc\n");
	uvc_stream_init_uvc(stream, fc);

	/* Main capture loop */
	events_loop(&events);

done:
	/* Cleanup */
	printf("uvc_stream_delete\n");
	uvc_stream_delete(stream);
	
	printf("video_source_destroy\n");
	video_source_destroy(src);
	
	printf("events_cleanup\n");
	events_cleanup(&events);
	
	printf("configfs_free_uvc_function\n");
	configfs_free_uvc_function(fc);

	return ret;
}