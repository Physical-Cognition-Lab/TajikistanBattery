"""The optional between-trial video break, closed with a second X press."""

from pathlib import Path


def show_pause_video(win, save_event):
    from psychopy import event, visual

    movie = visual.MovieStim(
        win, filename=str(Path(__file__).with_name("pause.avi")),
        units="pix", loop=True, autoStart=False,
    )
    try:
        movie.size = (1920, 1080)  # Fixed 16:9 break video size, in pixels.
        event.clearEvents(eventType="keyboard")
        print("Study paused: video playing. X = continue study.", flush=True)
        save_event("attgrabber")
        movie.play()
        while True:
            movie.draw()
            win.flip()
            if "x" in event.getKeys(keyList=["x"]):
                break
    finally:
        movie.unload()
    event.clearEvents(eventType="keyboard")
    win.flip()  # Clear the video before returning to the study.
    print("Continuing study.", flush=True)
