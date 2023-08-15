import gc
import queue
import sys

import torch
from PIL import Image
from diffusers import DiffusionPipeline, DPMSolverMultistepScheduler
from numpy import ndarray
from tqdm import tqdm

from manage_safety_checker import disable_safety_checker


class MirageGenerator:
    def __init__(self, auth_token, cache_dir="cache", use_cuda=True, disable_safety_checker_flag=True):
        self.auth_token = auth_token
        self.cache_dir = cache_dir
        self.queue = queue.Queue()
        self.use_cuda = use_cuda
        self.disable_safety_checker_flag = disable_safety_checker_flag

    def __enter__(self):
        self.__init_diffusion_pipe(self.use_cuda, self.disable_safety_checker_flag)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        del self.pipe
        self.pipe = None
        gc.collect()

    def __init_diffusion_pipe(self, use_cuda, disable_safety_checker_flag):
        print("Initializing Diffusion Pipeline")
        self.pipe = DiffusionPipeline.from_pretrained("cerspense/zeroscope_v2_576w",
                                                      use_auth_token=self.auth_token,
                                                      cache_dir=self.cache_dir,
                                                      torch_dtype=torch.float16,
                                                      use_safetensors=False,
                                                      variant="fp16")

        self.pipe.scheduler = DPMSolverMultistepScheduler.from_config(self.pipe.scheduler.config)

        if use_cuda:
            print("Using CUDA")
            self.pipe.to("cuda")
        else:
            print("Enabling CPU offload")
            self.pipe.enable_model_cpu_offload()

        # if using torch < 2.0
        #print("Enabling memory efficient attention")
        #self.pipe.enable_xformers_memory_efficient_attention()
        self.pipe.enable_vae_slicing()

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

    def generate(self, prompt, options):
        print(f"Generating mirage for prompt: {prompt}")
        self.pipe.progress_bar = self.progress_bar
        self.pipe.set_progress_bar_config(dynamic_ncols=False)

        height = 320
        width = 576
        steps = 150
        guidance_scale = 7.5
        rng_seed = 0
        num_frames = 36
        negative_prompt = None

        print("Using options: ", options)

        if 'height' in options:
            height = options['height']

        if 'width' in options:
            width = options['width']

        if 'steps' in options:
            try:
                steps = int(options['steps'])
            except ValueError:
                print(f"Steps '{options['steps']}' must be an integer")

        if 'guidance_scale' in options:
            try:
                guidance_scale = float(options['guidance_scale'])
            except ValueError:
                print(f"Guidance scale '{options['guidance_scale']}' must be a float")

        if 'seed' in options:
            try:
                rng_seed = int(options['seed'])
            except ValueError:
                print(f"Seed '{options['seed']}' must be an integer")

        if 'num_frames' in options:
            try:
                num_frames = int(options['num_frames'])
            except ValueError:
                print(f"Number of frames '{options['num_frames']}' must be an integer")

        if 'negative_prompt' in options:
            negative_prompt = options['negative_prompt']

        generator = torch.Generator(device="cuda").manual_seed(rng_seed)

        generated_video_frames = self.pipe(
            prompt=prompt,
            height=height,
            width=width,
            num_inference_steps=steps,
            guidance_scale=guidance_scale,
            generator=generator,
            num_frames=num_frames,
            #negative_prompt=negative_prompt
        ).frames
        print("Video generation complete")
        return generated_video_frames
