from moviepy.editor import VideoFileClip, vfx
import os
import logging
import uuid

# Configure logging
logger = logging.getLogger(__name__)

def make_video_unique(input_path):
    """
    Applies subtle effects using MoviePy to break hash/content-id matching.
    1. Speed: 1.03x (Affects both Video & Audio automatically)
    2. Contrast: +10%
    3. Gamma: 1.05
    4. Saturation: +10%
    5. Crop: Shifts pixel grid
    6. Volume: 95%
    """
    if not os.path.exists(input_path):
        logger.error(f"Input file not found: {input_path}")
        return None

    # Generate a new filename
    output_filename = f"processed_{uuid.uuid4()}.mp4"
    output_path = os.path.join(os.path.dirname(input_path), output_filename)
    
    logger.info(f"Processing video with MoviePy: {input_path} -> {output_path}")

    try:
        # 1. Load the Video
        clip = VideoFileClip(input_path)
        
        # 2. Apply Speed Effect (1.03x faster)
        # MoviePy handles audio pitch/sync automatically with speedx
        final_clip = clip.fx(vfx.speedx, 1.03)
        
        # 3. Apply Contrast Effect (Enhance luminosity/contrast slightly)
        # lum_contrast(lum=0, contrast=0.1) adds 10% contrast
        final_clip = final_clip.fx(vfx.lum_contrast, lum=0, contrast=0.1)

        # 4. Apply Gamma Correction (Subtle lighting change)
        # gamma < 1 makes shadows darker, > 1 makes them lighter. 1.05 is subtle.
        final_clip = final_clip.fx(vfx.gamma_corr, gamma=1.05)

        # 5. Apply Saturation Boost (Color intensity)
        # 1.10 = 10% more saturation
        final_clip = final_clip.fx(vfx.colorx, 1.10)

        # 6. Pixel Grid Shift (Cropping) - NEW
        # Cutting just 3 pixels off the edges shifts the entire coordinate system
        # which defeats exact-match visual hashing.
        w, h = final_clip.size
        final_clip = final_clip.crop(x1=3, y1=3, width=w-6, height=h-6)

        # 7. Volume Modification - NEW
        # Reduces volume slightly to change the waveform amplitude signature
        final_clip = final_clip.volumex(0.95)

        # 8. Audio Fades (Alters audio fingerprint at boundaries)
        final_clip = final_clip.audio_fadein(0.1).audio_fadeout(0.1)

        # 9. Write output file
        # codec='libx264' is standard for YouTube
        # audio_codec='aac' is required for sound
        # temp_audiofile is needed because MoviePy creates a temp wav file during processing
        final_clip.write_videofile(
            output_path, 
            codec='libx264', 
            audio_codec='aac', 
            temp_audiofile='temp-audio.m4a', 
            remove_temp=True, # Set to None to keep console clean, or 'bar' for progress bar
        )
        
        # Close the clips to release memory (Crucial on EC2)
        clip.close()
        final_clip.close()
        
        logger.info("Video processing complete.")
        return output_path

    except Exception as e:
        logger.error(f"MoviePy Processing Error: {e}")
        # Attempt to clean up resources if crash happens
        if 'clip' in locals(): clip.close()
        return None