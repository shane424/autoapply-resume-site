import platform
import subprocess
from app.models.job import Job


def open_in_browser(job: Job) -> None:
    url = job.apply_url
    system = platform.system()
    if system == "Darwin":
        cmd = ["open", url]
    elif system == "Windows":
        cmd = ["start", url]
    else:
        cmd = ["xdg-open", url]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
