import os
import subprocess
import json
import shutil
import platform
from PIL import Image, ImageDraw, ImageFont
from yt_compiler.thumbnail_maker import create_collage_thumbnail

# Add standard directories to PATH to ensure ffmpeg and ffprobe are found on macOS
extra_paths = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]
current_path = os.environ.get("PATH", "")
new_paths = [p for p in extra_paths if p not in current_path]
if new_paths:
    os.environ["PATH"] = os.pathsep.join(new_paths) + os.pathsep + current_path

def get_video_info(file_path):
    """
    Get video parameters (duration, width, height, fps, audio presence) using ffprobe.
    """
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=width,height,avg_frame_rate,duration,codec_type",
            "-show_entries", "format=duration",
            "-of", "json",
            file_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        data = json.loads(res.stdout)
        
        info = {
            "width": 1920,
            "height": 1080,
            "fps": 30.0,
            "duration": 0.0,
            "has_audio": False
        }
        
        streams = data.get("streams", [])
        for s in streams:
            codec_type = s.get("codec_type")
            if codec_type == "video":
                info["width"] = int(s.get("width", 1920))
                info["height"] = int(s.get("height", 1080))
                
                # Parse FPS
                fps_str = s.get("avg_frame_rate", "30/1")
                if "/" in fps_str:
                    num, den = fps_str.split("/")
                    if float(den) > 0:
                        info["fps"] = float(num) / float(den)
                else:
                    info["fps"] = float(fps_str)
                    
                if "duration" in s:
                    try:
                        info["duration"] = float(s["duration"])
                    except:
                        pass
            elif codec_type == "audio":
                info["has_audio"] = True
                
        # Fallback to format duration if stream duration is empty/0
        if info["duration"] == 0.0 and "format" in data:
            try:
                info["duration"] = float(data["format"].get("duration", 0.0))
            except:
                pass
                
        return info
    except Exception as e:
        print(f"Error reading video info for {file_path}: {e}")
        return {
            "width": 1920,
            "height": 1080,
            "fps": 30.0,
            "duration": 0.0,
            "has_audio": False
        }

def escape_ffmpeg_text(text):
    """
    Escape text characters for ffmpeg's drawtext filter.
    """
    text = text.replace('\\', '\\\\')
    text = text.replace("'", "'\\\\''")
    text = text.replace(':', '\\:')
    text = text.replace('%', '\\%')
    return text

def normalize_video(input_path, output_path, codec, preset_args, width=1280, height=720, bg_style="blur", bg_color="#000000"):
    """
    Normalizes a single video file to target width x height.
    (Retained for backward compatibility / external imports).
    """
    info = get_video_info(input_path)
    aspect = info["width"] / info["height"] if info["height"] > 0 else 1.777
    is_landscape_16_9 = abs(aspect - (16.0 / 9.0)) < 0.01

    if info["has_audio"]:
        audio_input_args = ["-i", input_path]
        audio_filter = "[0:a]aformat=sample_rates=44100:channel_layouts=stereo[a]"
    else:
        audio_input_args = [
            "-i", input_path,
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"
        ]
        audio_filter = "aformat=sample_rates=44100:channel_layouts=stereo[a]"

    if is_landscape_16_9:
        video_filter = f"[0:v]scale={width}:{height},fps=30,format=yuv420p[v]"
    else:
        if bg_style == "solid":
            video_filter = (
                f"color=c='{bg_color}':s={width}x{height},fps=30[bg];"
                f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1,setsar=1,fps=30,format=yuv420p[v]"
            )
        else:
            video_filter = (
                f"[0:v]scale=128:72:force_original_aspect_ratio=increase,crop=128:72,boxblur=3:3,scale={width}:{height}[bg];"
                f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease[fg];"
                f"[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1,setsar=1,fps=30,format=yuv420p[v]"
            )

    filter_complex = f"{video_filter};{audio_filter}" if info["has_audio"] else video_filter

    cmd = ["ffmpeg", "-y"] + audio_input_args + [
        "-filter_complex", filter_complex,
        "-map", "[v]"
    ]
    if info["has_audio"]:
        cmd += ["-map", "[a]"]
    else:
        cmd += ["-map", "1:a", "-shortest"]

    cmd += [
        "-c:v", codec
    ] + preset_args + [
        "-c:a", "aac",
        "-b:a", "192k",
        output_path
    ]

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        if codec == "h264_videotoolbox":
            fallback_cmd = [c if c != "h264_videotoolbox" else "libx264" for c in cmd]
            idx_codec = fallback_cmd.index("libx264")
            fallback_cmd = fallback_cmd[:idx_codec+1] + ["-preset", "superfast", "-crf", "20"] + fallback_cmd[idx_codec+1:]
            res2 = subprocess.run(fallback_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res2.returncode == 0:
                return True
        print(f"Error normalizing video: {res.stderr.decode('utf-8', errors='ignore')}")
        return False
    return True

def compile_videos_batch(
    video_paths,
    output_dir,
    min_duration=480,
    max_duration=600,
    shuffle=False,
    text_overlays=None,
    watermarks=None,
    progress_callback=None,
    stop_event=None,
    intro_path=None,
    outro_path=None,
    bgm_path=None,
    bgm_volume=0.15,
    bg_style="blur",
    bg_color="#000000",
    normalize_audio=False,
    bypass_bgm_copyright=True,
    silent_music_path=None,
    width=1280,
    height=720,
    auto_make_thumbnail=False,
    thumbnail_title_template="",
    thumbnail_start_index=1,
    speed=1.0,
    voice_effect="Bình thường",
    dyn_bg_path=None,
    thumbnail_border_color="#FE640B",
    thumbnail_text_color="#FFFF00",
    custom_thumbnail_path=None,
    thumbnail_font_size=44,
    thumbnail_banner_color="white",
    thumbnail_frame_offsets=[15.0, 33.0, 85.0]
):
    """
    CapCut-Style Single-Pass batch compiler.
    Combines, normalizes aspect ratios, blends background borders, mixes BGM, overlays watermarks and text layers, 
    and encodes the final segment directly IN-MEMORY with a single FFmpeg render pass.
    """
    if text_overlays is None:
        text_overlays = []
    if watermarks is None:
        watermarks = []

    os.makedirs(output_dir, exist_ok=True)
    temp_dir = os.path.join(output_dir, "temp_compiler")
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    try:
        codec = "h264_videotoolbox" if platform.system() == "Darwin" else "libx264"
        preset_args = [] if codec == "h264_videotoolbox" else ["-preset", "ultrafast", "-crf", "23", "-threads", "0"]

        if progress_callback:
            progress_callback("Scanning video files...", 0.05)

        # Get details for intro and outro (Ignored / disabled by user request)
        intro_info = None
        outro_info = None
        
        intro_dur = 0.0
        outro_dur = 0.0
        base_dur = 0.0

        # Scan input sub-videos in parallel for maximum speed!
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        valid_videos = []
        existing_paths = [p for p in video_paths if os.path.exists(p)]
        total_existing = len(existing_paths)
        
        if progress_callback:
            progress_callback(f"Scanning {total_existing} video files in parallel...", 0.05)
            
        def scan_single_path(path):
            if stop_event and stop_event.is_set():
                return None
            try:
                info = get_video_info(path)
                if info and info.get("duration", 0) > 0:
                    return {"path": path, "info": info}
            except:
                pass
            return None

        # Use 16 parallel workers to load file metadata
        max_workers = min(16, max(1, total_existing))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {p: executor.submit(scan_single_path, p) for p in existing_paths}
            for i, path in enumerate(existing_paths):
                if stop_event and stop_event.is_set():
                    executor.shutdown(wait=False)
                    raise InterruptedError("Stopped by user.")
                future = futures[path]
                res = future.result()
                if res:
                    valid_videos.append(res)
                if progress_callback and i % 50 == 0:
                    progress_callback(f"Scanning video files ({i}/{total_existing})...", 0.05 + 0.1 * (i / total_existing))

        if not valid_videos:
            raise ValueError("No valid video files to compile.")

        if shuffle:
            import random
            random.shuffle(valid_videos)

        # Group videos based on duration
        groups = []
        current_group = []
        current_duration = base_dur

        for item in valid_videos:
            v_dur = item["info"]["duration"]
            if current_duration + v_dur > max_duration and current_group:
                groups.append(current_group)
                current_group = [item]
                current_duration = base_dur + v_dur
            else:
                current_group.append(item)
                current_duration += v_dur

        if current_group:
            groups.append(current_group)

        total_groups = len(groups)
        compiled_files = []

        # Process each group in a single-pass CapCut-style pipeline
        for g_idx, group in enumerate(groups):
            if stop_event and stop_event.is_set():
                raise InterruptedError("Stopped by user.")

            # Move clips without audio to the end of the group
            sound_clips = [item for item in group if item["info"].get("has_audio", False)]
            silent_clips = [item for item in group if not item["info"].get("has_audio", False)]
            group = sound_clips + silent_clips

            msg = f"Compiling segment {g_idx+1}/{total_groups} (Single-Pass)..."
            percent = 0.10 + (g_idx / total_groups) * 0.85
            if progress_callback:
                progress_callback(msg, percent)

            # Build inputs list: segment_clips = intro + group + outro
            segment_clips = []
            if intro_info:
                segment_clips.append({"path": intro_path, "info": intro_info})
            segment_clips.extend(group)
            if outro_info:
                segment_clips.append({"path": outro_path, "info": outro_info})
            total_duration = sum(item["info"]["duration"] / speed for item in segment_clips)

            cmd = ["ffmpeg", "-y"]
            
            # 1. Add video inputs
            for item in segment_clips:
                cmd.extend(["-i", item["path"]])

            # 1b. Add dynamic background input (Video or Image)
            dyn_bg_active = dyn_bg_path and os.path.exists(dyn_bg_path)
            is_dyn_bg_video = False
            if dyn_bg_active:
                ext = os.path.splitext(dyn_bg_path)[1].lower()
                is_dyn_bg_video = ext in ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.ts', '.3gp', '.m4v')
                if is_dyn_bg_video:
                    cmd.extend(["-i", dyn_bg_path])
                else:
                    cmd.extend(["-loop", "1", "-i", dyn_bg_path])
                dyn_bg_input_idx = len(segment_clips)

            # 2. Add BGM input
            bgm_active = bgm_path and os.path.exists(bgm_path)
            if bgm_active:
                cmd.extend(["-stream_loop", "-1", "-i", bgm_path])
                bgm_input_idx = len(segment_clips) + (1 if dyn_bg_active else 0)

            # 2b. Add silent fallback music input
            silent_music_active = silent_music_path and os.path.exists(silent_music_path)
            if silent_music_active:
                cmd.extend(["-stream_loop", "-1", "-i", silent_music_path])
                silent_music_input_idx = len(segment_clips) + (1 if dyn_bg_active else 0) + (1 if bgm_active else 0)

            # 3. Add watermark inputs (prepared in PIL)
            scale_factor = width / 1920.0
            temp_wm_paths = []
            for w_idx, wm in enumerate(watermarks):
                wm_path = wm["path"]
                if not os.path.exists(wm_path):
                    continue
                try:
                    img = Image.open(wm_path).convert("RGBA")
                    scaled_wm_w = int(wm["w"] * scale_factor)
                    scaled_wm_h = int(wm["h"] * scale_factor)
                    img = img.resize((scaled_wm_w, scaled_wm_h), Image.Resampling.LANCZOS)
                    alpha = img.split()[3]
                    alpha = alpha.point(lambda p: int(p * wm["opacity"]))
                    img.putalpha(alpha)
                    
                    temp_wm_path = os.path.join(temp_dir, f"temp_wm_{g_idx}_{w_idx}.png")
                    img.save(temp_wm_path)
                    temp_wm_paths.append(temp_wm_path)
                    cmd.extend(["-i", temp_wm_path])
                except Exception as e:
                    print(f"Error preparing watermark: {e}")

            wm_start_idx = len(segment_clips) + (1 if dyn_bg_active else 0) + (1 if bgm_active else 0) + (1 if silent_music_active else 0)

            # Build Filter Complex
            filter_parts = []
            
            # Format and convert each clip in the filter complex on the fly
            for i, item in enumerate(segment_clips):
                info = item["info"]
                aspect = info["width"] / info["height"] if info["height"] > 0 else 1.777
                is_landscape_16_9 = abs(aspect - (16.0 / 9.0)) < 0.01
                
                v_dur = info["duration"] / speed
                v_speed_filter = f",setpts=PTS/{speed}" if speed != 1.0 else ""
                
                v_out = f"[v_conv{i}]"
                if is_landscape_16_9:
                    filter_parts.append(f"[{i}:v]scale={width}:{height}{v_speed_filter},fps=30,format=yuv420p{v_out}")
                else:
                    if dyn_bg_active:
                        if is_dyn_bg_video:
                            filter_parts.append(
                                f"[{dyn_bg_input_idx}:v]scale={width}:{height},loop=loop=-1:size=32767:start=0,trim=end={v_dur},setpts=PTS-STARTPTS[bg_dyn{i}];"
                                f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease{v_speed_filter}[fg{i}];"
                                f"[bg_dyn{i}][fg{i}]overlay=(W-w)/2:(H-h)/2:shortest=1,setsar=1,fps=30,format=yuv420p{v_out}"
                            )
                        else:
                            filter_parts.append(
                                f"[{dyn_bg_input_idx}:v]scale={width}:{height},trim=end={v_dur},setpts=PTS-STARTPTS[bg_dyn{i}];"
                                f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease{v_speed_filter}[fg{i}];"
                                f"[bg_dyn{i}][fg{i}]overlay=(W-w)/2:(H-h)/2:shortest=1,setsar=1,fps=30,format=yuv420p{v_out}"
                            )
                    elif bg_style == "solid":
                        filter_parts.append(
                            f"color=c='{bg_color}':s={width}x{height},fps=30,trim=end={v_dur}[bg{i}];"
                            f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease{v_speed_filter}[fg{i}];"
                            f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2:shortest=1,setsar=1,fps=30,format=yuv420p{v_out}"
                        )
                    else:
                        filter_parts.append(
                            f"[{i}:v]scale=128:72:force_original_aspect_ratio=increase,crop=128:72,boxblur=3:3,scale={width}:{height}{v_speed_filter}[bg{i}];"
                            f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease{v_speed_filter}[fg{i}];"
                            f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2:shortest=1,setsar=1,fps=30,format=yuv420p{v_out}"
                        )

                a_out = f"[a_conv{i}]"
                if info["has_audio"]:
                    a_filters = ["aformat=sample_rates=44100:channel_layouts=stereo", "aresample=async=1"]
                    if speed != 1.0:
                        if speed <= 2.0:
                            a_filters.append(f"atempo={speed}")
                        else:
                            a_filters.append(f"atempo=2.0,atempo={speed/2.0}")
                    
                    if voice_effect == "Giọng Chipmunk":
                        a_filters.append("asetrate=44100*1.35,atempo=1/1.35")
                    elif voice_effect == "Giọng Trầm/Robot":
                        a_filters.append("asetrate=44100*0.72,atempo=1/0.72")
                    elif voice_effect == "Rung giọng":
                        a_filters.append("asetremolo=f=8:d=0.9")
                    elif voice_effect == "Méo tiếng":
                        a_filters.append("apulsator=hz=6:amount=0.8")
                        
                    a_chain = ",".join(a_filters)
                    filter_parts.append(f"[{i}:a]{a_chain}{a_out}")
                else:
                    if silent_music_active:
                        filter_parts.append(f"[{silent_music_input_idx}:a]atrim=end={v_dur},asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=stereo,aresample=async=1{a_out}")
                    else:
                        filter_parts.append(f"anullsrc=channel_layout=stereo:sample_rate=44100,atrim=end={v_dur}{a_out}")

            # Concatenate all streams in-memory
            concat_in = ""
            for i in range(len(segment_clips)):
                concat_in += f"[v_conv{i}][a_conv{i}]"
            filter_parts.append(f"{concat_in}concat=n={len(segment_clips)}:v=1:a=1[vconcat][aconcat]")

            # Apply watermarks
            v_curr = "[vconcat]"
            for w_idx in range(len(temp_wm_paths)):
                wm_stream_in = f"[{wm_start_idx + w_idx}:v]"
                v_next = f"[v_wm_{w_idx}]"
                wm_x = int(watermarks[w_idx]["x"] * scale_factor)
                wm_y = int(watermarks[w_idx]["y"] * scale_factor)
                filter_parts.append(f"{v_curr}{wm_stream_in}overlay=x={wm_x}:y={wm_y}{v_next}")
                v_curr = v_next

            # Apply text layers (as transparent PNG overlays)
            temp_txt_paths = []
            for t_idx, txt_info in enumerate(text_overlays):
                text_str = txt_info["text"]
                # Dynamic replacement of segment index
                text_str = text_str.replace("{index}", str(thumbnail_start_index + g_idx))
                if not text_str.strip():
                    continue
                
                f_path = txt_info.get("font_path", "")
                if not f_path or not os.path.exists(f_path):
                    f_path = "/System/Library/Fonts/Helvetica.ttc"
                    
                font_size = int(txt_info.get("size", 40) * scale_factor)
                
                try:
                    font = ImageFont.truetype(f_path, font_size)
                except:
                    font = ImageFont.load_default()
                    
                # Measure text size
                draw_dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
                try:
                    bbox = draw_dummy.textbbox((0, 0), text_str, font=font)
                    tw = bbox[2] - bbox[0]
                    th = bbox[3] - bbox[1]
                    offset_x = bbox[0]
                    offset_y = bbox[1]
                except:
                    tw, th = draw_dummy.textsize(text_str, font=font)
                    offset_x, offset_y = 0, 0
                    
                pad = max(10, int(font_size * 0.4))
                w_img = tw + pad * 2
                h_img = th + pad * 2
                
                txt_canvas = Image.new("RGBA", (w_img, h_img), (0,0,0,0))
                draw = ImageDraw.Draw(txt_canvas)
                
                # 1. Background Box
                if txt_info.get("bg_box_enabled", False):
                    bg_color = txt_info.get("bg_box_color", "#000000")
                    bg_alpha = int(txt_info.get("bg_box_opacity", 0.6) * 255)
                    h_val = bg_color.lstrip('#')
                    rgb = tuple(int(h_val[i:i+2], 16) for i in (0, 2, 4))
                    draw.rectangle(
                        [(pad - 4, pad - 4), (pad + tw + 4, pad + th + 4)],
                        fill=rgb + (bg_alpha,)
                    )
                    
                # 2. Drop Shadow
                if txt_info.get("shadow_enabled", False):
                    sh_color = txt_info.get("shadow_color", "#000000")
                    sh_offset = int(txt_info.get("shadow_offset", 4) * scale_factor)
                    h_val = sh_color.lstrip('#')
                    rgb = tuple(int(h_val[i:i+2], 16) for i in (0, 2, 4))
                    draw.text((pad - offset_x + sh_offset, pad - offset_y + sh_offset), 
                              text_str, font=font, fill=rgb + (255,))
                              
                # 3. Main text with border/stroke
                stroke_w = int(txt_info.get("stroke_width", 3) * scale_factor)
                stroke_color = txt_info.get("border_color", "#000000")
                fill_color = txt_info.get("color", "#FFFF00")
                
                draw.text((pad - offset_x, pad - offset_y), text_str, font=font, 
                          fill=fill_color, stroke_width=stroke_w, stroke_fill=stroke_color)
                          
                # 4. Rotate text image
                angle = float(txt_info.get("angle", 0))
                if angle != 0:
                    rotated_img = txt_canvas.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
                else:
                    rotated_img = txt_canvas
                    
                # Paste onto full-resolution canvas
                full_frame = Image.new("RGBA", (width, height), (0,0,0,0))
                target_x = int(txt_info["x"] * scale_factor)
                target_y = int(txt_info["y"] * scale_factor)
                
                rw, rh = rotated_img.size
                paste_x = target_x - rw // 2
                paste_y = target_y - rh // 2
                
                full_frame.paste(rotated_img, (paste_x, paste_y), rotated_img)
                
                temp_txt_path = os.path.join(temp_dir, f"temp_txt_{g_idx}_{t_idx}.png")
                full_frame.save(temp_txt_path)
                temp_txt_paths.append(temp_txt_path)
                cmd.extend(["-i", temp_txt_path])
                
            # Add text overlay inputs to filter complex
            txt_start_idx = wm_start_idx + len(temp_wm_paths)
            for t_idx in range(len(temp_txt_paths)):
                txt_stream_in = f"[{txt_start_idx + t_idx}:v]"
                v_next = f"[v_txt_{t_idx}]"
                filter_parts.append(f"{v_curr}{txt_stream_in}overlay=x=0:y=0{v_next}")
                v_curr = v_next

            # Mix audio and BGM
            a_curr = "[aconcat]"
            if normalize_audio:
                filter_parts.append(f"[aconcat]dynaudnorm[main_normalized]")
                a_curr = "[main_normalized]"

            if bgm_active:
                if bypass_bgm_copyright:
                    # Apply copyright bypass filters to BGM stream
                    filter_parts.append(f"[{bgm_input_idx}:a]volume={bgm_volume},asetrate=44100*1.04,aresample=44100,aphaser=type=t:speed=2:decay=0.4,tremolo=f=4.0:d=0.2[bgm_vol]")
                else:
                    filter_parts.append(f"[{bgm_input_idx}:a]volume={bgm_volume}[bgm_vol]")
                filter_parts.append(f"{a_curr}[bgm_vol]amix=inputs=2:duration=first:dropout_transition=2[a_mixed]")
                a_curr = "[a_mixed]"

            # Map outputs
            cmd.extend(["-filter_complex", ";".join(filter_parts)])
            cmd.extend(["-map", v_curr, "-map", a_curr])

            if thumbnail_title_template:
                clean_template = thumbnail_title_template
                for char in ['|', '/', '\\', ':', '*', '?', '"', '<', '>']:
                    clean_template = clean_template.replace(char, '-')
                
                curr_part_idx = thumbnail_start_index + g_idx
                if "{index}" in clean_template:
                    final_name = clean_template.replace("{index}", str(curr_part_idx)) + ".mp4"
                else:
                    final_name = f"{clean_template} - Phần {curr_part_idx}.mp4"
            else:
                final_name = f"Youtube_Compiled_{g_idx+1:02d}.mp4"
                
            final_output_path = os.path.join(output_dir, final_name)

            cmd.extend([
                "-c:v", codec
            ] + preset_args + [
                "-c:a", "aac",
                "-b:a", "192k",
                "-t", f"{total_duration:.3f}",
                final_output_path
            ])

            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode != 0:
                if codec == "h264_videotoolbox":
                    fallback_cmd = [c if c != "h264_videotoolbox" else "libx264" for c in cmd]
                    idx_codec = fallback_cmd.index("libx264")
                    fallback_cmd = fallback_cmd[:idx_codec+1] + ["-preset", "ultrafast", "-crf", "23", "-threads", "0"] + fallback_cmd[idx_codec+1:]
                    res2 = subprocess.run(fallback_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    if res2.returncode == 0:
                        compiled_files.append(final_output_path)
                        continue
                print(f"Single-pass compile failed: {res.stderr.decode('utf-8', errors='ignore')}")
                raise RuntimeError("Failed to compile segment in single-pass.")

            compiled_files.append(final_output_path)

            if auto_make_thumbnail:
                try:
                    # Create a dedicated directory for thumbnails inside output_dir
                    thumb_dir = os.path.join(output_dir, "Anh_Bia_Thumbnails")
                    os.makedirs(thumb_dir, exist_ok=True)
                    
                    thumb_name = os.path.splitext(final_name)[0] + ".jpg"
                    thumb_path = os.path.join(thumb_dir, thumb_name)
                    
                    if g_idx == 0 and custom_thumbnail_path and os.path.exists(custom_thumbnail_path):
                        # Copy imported custom thumbnail directly for the first video
                        shutil.copy2(custom_thumbnail_path, thumb_path)
                    elif thumbnail_title_template:
                        # Auto-create 3-box collage thumbnail
                        curr_part_idx = thumbnail_start_index + g_idx
                        thumb_text = thumbnail_title_template.replace("{index}", str(curr_part_idx))
                        group_paths = [item["path"] for item in group]
                        
                        stroke_hex = "#450a0a" if thumbnail_text_color == "#D20F39" else "#000000"
                        create_collage_thumbnail(
                            group_paths, 
                            thumb_text, 
                            thumb_path,
                            banner_border_color=thumbnail_border_color,
                            text_fill_color=thumbnail_text_color,
                            text_stroke_color=stroke_hex,
                            frame_percentages=thumbnail_frame_offsets,
                            font_size=thumbnail_font_size,
                            banner_bg_color=thumbnail_banner_color
                        )
                except Exception as thumb_err:
                    print(f"Error making automatic compile thumbnail: {thumb_err}")

        if progress_callback:
            progress_callback("Clean up temporary files...", 0.98)

        shutil.rmtree(temp_dir, ignore_errors=True)

        if progress_callback:
            progress_callback(f"Successfully compiled {len(compiled_files)} videos!", 1.0)

        return compiled_files

    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise e
