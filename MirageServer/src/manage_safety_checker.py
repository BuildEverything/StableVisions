def dummy(_images, **kwargs):
    return _images, False


def disable_safety_checker(pipe):
    pipe.safety_checker = dummy

