import commune as c
import torch
from diffusers import StableDiffusionPipeline, StableDiffusionImg2ImgPipeline, StableDiffusionInpaintPipelineLegacy, DDIMScheduler, AutoencoderKL
from PIL import Image

from ip_adapter import IPAdapterFull

base_model_path = "SG161222/Realistic_Vision_V4.0_noVAE"
vae_model_path = "stabilityai/sd-vae-ft-mse"
image_encoder_path = "models/image_encoder/"
ip_ckpt = "models/ip-adapter-full-face_sd15.bin"
device = "cuda"




class Demo(c.Module):
    def __init__(self, a=1, b=2):
        self.set_config(kwargs=locals())
                
        self.noise_scheduler = DDIMScheduler(
            num_train_timesteps=1000,
            beta_start=0.00085,
            beta_end=0.012,
            beta_schedule="scaled_linear",
            clip_sample=False,
            set_alpha_to_one=False,
            steps_offset=1,
        )
        self.vae = AutoencoderKL.from_pretrained(vae_model_path).to(dtype=torch.float16)

        # load SD pipeline
        self.pipe = StableDiffusionPipeline.from_pretrained(
            base_model_path,
            torch_dtype=torch.float16,
            scheduler=self.noise_scheduler,
            vae=self.vae,
            feature_extractor=None,
            safety_checker=None
        )
        self.ip_model = IPAdapterFull(self.pipe, image_encoder_path, ip_ckpt, device, num_tokens=257)

    def call(self, x:int = 1, y:int = 2) -> int:
        c.print(self.config)
        c.print(self.config, 'This is the config, it is a Munch object')
        return x + y
    
    def generate(self, imgUrl="assets/images/ai_face.png", promptText="wearing sunglases") :      
        # read image prompt
        image = Image.open(imgUrl)
        image.resize((256, 256))

        # use face as image prompt
        images = self.ip_model.generate(
            pil_image=image, num_samples=4, prompt=promptText,
            scale=0.7, width=512, height=512, num_inference_steps=50, seed=42)
        
        for i, image in enumerate(images):
            image.save(f"{i}.png")

        c.print("File created. 0.png, 1.png, 2.png, 3.png")
        return images