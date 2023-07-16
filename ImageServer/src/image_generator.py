import asyncio
import queue
import sys
import threading

import torch
from PIL import Image
from diffusers import DiffusionPipeline
from tqdm import tqdm

from manage_safety_checker import disable_safety_checker


class ImageGenerator:
    def __init__(self, auth_token, cache_dir="cache", use_cuda=True, disable_safety_checker_flag=True):
        self.auth_token = auth_token
        self.cache_dir = cache_dir
        self.queue = queue.Queue()
        self.__init_diffusion_pipe(use_cuda, disable_safety_checker_flag)

    def __init_diffusion_pipe(self, use_cuda, disable_safety_checker_flag):
        print("Initializing Diffusion Pipeline")
        self.pipe = DiffusionPipeline.from_pretrained("stabilityai/stable-diffusion-xl-base-0.9",
                                                      use_auth_token=self.auth_token,
                                                      cache_dir=self.cache_dir,
                                                      torch_dtype=torch.float16,
                                                      use_safetensors=False,
                                                      variant="fp16")

        if use_cuda:
            print("Using CUDA")
            self.pipe.to("cuda")
        else:
            print("Enabling CPU offload")
            self.pipe.enable_model_cpu_offload()

        # if using torch < 2.0
        print("Enabling memory efficient attention")
        self.pipe.enable_xformers_memory_efficient_attention()

        if disable_safety_checker_flag:
            print("Disabling safety checker")
            disable_safety_checker(self.pipe)

    def progress_bar(self, iterable=None, total=None):
        if not hasattr(self, "_progress_bar_config"):
            self._progress_bar_config = {}
        elif not isinstance(self._progress_bar_config, dict):
            raise ValueError(
                f"`self._progress_bar_config` should be of type `dict`, but is {type(self._progress_bar_config)}."
            )

        if iterable is not None:
            print("using iterable: ", iterable)
            return tqdm(iterable, **self._progress_bar_config, file=sys.stderr)
        elif total is not None:
            print("using total: ", total)
            return tqdm(total=total, **self._progress_bar_config, file=sys.stderr)
        else:
            raise ValueError("Either `total` or `iterable` has to be defined.")

    def generate(self, prompt, websocket) -> [Image]:
        print(f"Generating image for prompt: {prompt}")
        self.pipe.progress_bar = self.progress_bar
        self.pipe.set_progress_bar_config(dynamic_ncols=False)
        generated_images = self.pipe(prompt=prompt).images
        print("Image generation complete")
        return generated_images
