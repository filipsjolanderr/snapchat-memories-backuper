from __future__ import annotations

from pathlib import Path

from tqdm import tqdm

from .config import AppConfig
from .download import Downloader
from .executors import (
    CombineService,
    CopyService,
    RenameService,
    ZipService,
)
from .fs import detect_and_fix_zip_files, find_zip_files_top_level
from .logger import error, info, warning
from .metadata import apply_metadata_to_outputs, parse_memories_html
from .planner import Planner
from .simulator import DryRunSimulator
from .stats import count_input_breakdown, count_output_memories
from .utils import ensure_dir, managed_tmp_dir


class Pipeline:
    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self.planner = Planner()
        self.zips = ZipService()
        self.copier = CopyService()
        self.renamer = RenameService()
        self.combiner = CombineService(cfg)
        self.downloader = Downloader(cfg.download_workers)
        self.simulator = DryRunSimulator() if cfg.dry_run else None

    def run_auto(self) -> int:
        assert self.cfg.input_path is not None
        inp = self.cfg.input_path
        
        # Validate input path exists
        if not inp.exists():
            error(f"Input path does not exist: {inp}")
            return 2
        
        if inp.suffix.lower() == ".html":
            if not inp.is_file():
                error(f"Input HTML path is not a file: {inp}")
                return 2
            return self.run_download_mode(inp)
        
        if inp.is_dir():
            return self.run_folder_mode(inp)
        
        error(f"Input must be an HTML file or a folder: {inp}")
        return 2

    def run_download_mode(self, html_path: Path) -> int:
        # Validate HTML file exists and is readable
        if not html_path.exists():
            error(f"HTML file not found: {html_path}")
            return 2
        
        if not html_path.is_file():
            error(f"HTML path is not a file: {html_path}")
            return 2
        
        try:
            if html_path.stat().st_size == 0:
                error(f"HTML file is empty: {html_path}")
                return 2
        except (OSError, PermissionError) as e:
            error(f"Cannot access HTML file: {html_path}", e)
            return 2
        
        out = (
            self.cfg.output_dir
            if self.cfg.output_dir
            else Path("output").resolve()
        )
        
        try:
            if self.simulator:
                self.simulator.simulate_ensure_dir(out)
            else:
                ensure_dir(out, False)
        except (OSError, PermissionError) as e:
            error(f"Cannot create output directory: {out}", e)
            return 2

        info(f"📥 Downloading memories from {html_path}")
        try:
            items = self.downloader.plan(html_path)
        except Exception as e:
            error(f"Failed to parse HTML file: {html_path}", e)
            return 1
        
        if not items:
            warning("No download items found in HTML file")
            return 0
        
        try:
            if self.simulator:
                imgs_dl, vids_dl = self.simulator.simulate_download(items)
            else:
                imgs_dl, vids_dl = self.downloader.download_all(
                    items, out, False
                )
        except KeyboardInterrupt:
            error("Download interrupted by user")
            return 130
        except Exception as e:
            error("Failed to download files", e)
            return 1
        
        info(f"📸 Images downloaded: {imgs_dl}")
        info(f"🎬 Videos downloaded: {vids_dl}")

        info("🔄 Processing downloaded files...")
        tmp_root = out / ".tmp_work"
        if self.simulator:
            self.simulator.simulate_create_temp_dir(tmp_root)
            tmp = tmp_root  # Use the path directly in dry run
            # Fix ZIP files
            # In dry run, we can't actually detect files, so simulate based on plans
            try:
                extract_plans_later = self.planner.plan_zip_extractions(out, tmp)
                if extract_plans_later:
                    self.simulator.simulate_fix_zip_files(len(extract_plans_later))
            except FileNotFoundError:
                # Directory doesn't exist in dry run, skip
                pass

            try:
                extract_plans = self.planner.plan_zip_extractions(out, tmp)
                if extract_plans:
                    self.simulator.simulate_extract_zips(extract_plans)
            except FileNotFoundError:
                # Directory doesn't exist in dry run, skip
                pass

            # Standalone mp4 copy (downloaded files are already at out)
            try:
                copy_plans = self.planner.plan_copy_standalone_mp4s(out, out)
                if copy_plans:
                    self.simulator.simulate_copy_mp4s(copy_plans)
            except FileNotFoundError:
                # Directory doesn't exist in dry run, skip
                pass

            # Unnamed files in out and tmp
            try:
                ren1 = self.planner.plan_unlabeled_renames(out, out, None)
                if ren1:
                    self.simulator.simulate_rename_files(ren1)
            except FileNotFoundError:
                # Directory doesn't exist in dry run, skip
                pass

            try:
                ren2 = self.planner.plan_unlabeled_renames(tmp, tmp, None)
                if ren2:
                    self.simulator.simulate_rename_files(ren2)
            except FileNotFoundError:
                # Directory doesn't exist in dry run, skip
                pass

            # Combine only ZIP contents
            try:
                combine_plans = self.planner.plan_filesystem_combinations(tmp, out)
                if combine_plans:
                    try:
                        img_done, vid_done = self.simulator.simulate_combine_files(
                            combine_plans,
                            self.cfg.image_workers,
                            self.cfg.video_workers,
                        )
                    except Exception as e:
                        error("Failed to simulate combine files", e)
                        return 1
            except FileNotFoundError:
                # Directory doesn't exist in dry run, skip
                pass

            # Apply metadata after combining (on all final files)
            try:
                img_tag, vid_tag = self.simulator.simulate_apply_metadata(
                    html_path, out
                )
                if img_tag > 0 or vid_tag > 0:
                    info(
                        f"🧭 Would apply metadata → images: {img_tag}, "
                        f"videos: {vid_tag}"
                    )
            except Exception as e:
                warning(f"Failed to simulate metadata: {e}")

            # Remove ZIP files after extraction
            try:
                zip_files = find_zip_files_top_level(out)
                if zip_files:
                    self.simulator.simulate_remove_zips(zip_files)
            except FileNotFoundError:
                # Directory doesn't exist in dry run, skip
                pass
        else:
            try:
                with managed_tmp_dir(tmp_root, False) as tmp:
                    fixed = detect_and_fix_zip_files(out)
                    if fixed:
                        info(f"🔧 Fixed {fixed} ZIP files with wrong extensions")

                    extract_plans = self.planner.plan_zip_extractions(out, tmp)
                    if extract_plans:
                        info(f"📦 Extracting {len(extract_plans)} ZIP files...")
                        try:
                            _ = self.zips.run(extract_plans, False)
                        except Exception as e:
                            error("Failed to extract ZIP files", e)
                            return 1

                    # Standalone mp4 copy (downloaded files are already at out)
                    copy_plans = self.planner.plan_copy_standalone_mp4s(out, out)
                    if copy_plans:
                        try:
                            _ = self.copier.run(copy_plans, False)
                        except Exception as e:
                            error("Failed to copy MP4 files", e)
                            return 1

                    # Unnamed files in out and tmp
                    ren1 = self.planner.plan_unlabeled_renames(out, out, None)
                    ren2 = self.planner.plan_unlabeled_renames(tmp, tmp, None)
                    if ren1 or ren2:
                        try:
                            if ren1:
                                _ = self.renamer.run(ren1, False)
                            if ren2:
                                _ = self.renamer.run(ren2, False)
                        except Exception as e:
                            error("Failed to rename files", e)
                            return 1

                    # Combine only ZIP contents
                    combine_plans = self.planner.plan_filesystem_combinations(tmp, out)

                    # Combine
                    if combine_plans:
                        try:
                            img_done, vid_done = self.combiner.run(
                                combine_plans,
                                False,
                                self.cfg.image_workers,
                                self.cfg.video_workers,
                            )
                        except KeyboardInterrupt:
                            error("Processing interrupted by user")
                            return 130
                        except Exception as e:
                            error("Failed to combine files", e)
                            return 1

                    # Apply metadata after combining (on all final files)
                    try:
                        meta = parse_memories_html(html_path)
                        if meta:
                            info(f"🧭 Applying metadata...")
                            img_tag, vid_tag = apply_metadata_to_outputs(out, meta, self.cfg.metadata_workers)
                            info(
                                f"🧭 Metadata applied → images: {img_tag}, "
                                f"videos: {vid_tag}"
                            )
                    except Exception as e:
                        warning(f"Failed to apply metadata: {e}")

                    # Remove ZIP files after extraction
                    zip_files = find_zip_files_top_level(out)
                    if zip_files:
                        removed_count = 0
                        for zip_file in zip_files:
                            try:
                                zip_file.unlink()
                                removed_count += 1
                            except Exception as e:
                                warning(f"Failed to remove ZIP file {zip_file.name}: {e}")
                        if removed_count > 0:
                            info(f"🗑️ ZIP files removed: {removed_count}")
            except Exception as e:
                error("Failed to process files", e)
                return 1

        # Clean residual temp dirs created by encoders (only in real mode)
        if not self.simulator:
            for t in out.glob("temp_*"):
                try:
                    import shutil
                    shutil.rmtree(t, ignore_errors=True)
                except Exception:
                    pass

        info("\n✅ Download and processing complete!" if not self.cfg.dry_run else "\n✅ Download plan complete!")
        info(f"📁 Output folder: {out}")
        info(f"📸 Images downloaded: {imgs_dl}")
        info(f"🎬 Videos downloaded: {vids_dl}")
        if not self.cfg.dry_run:
            try:
                info(f"⬇️ Output Memories: {count_output_memories(out)}")
            except Exception as e:
                warning(f"Failed to count output memories: {e}")
        return 0

    def run_folder_mode(self, input_folder: Path) -> int:
        # Validate input folder exists
        if not input_folder.exists():
            error(f"Input folder does not exist: {input_folder}")
            return 2
        
        if not input_folder.is_dir():
            error(f"Input path is not a directory: {input_folder}")
            return 2
        
        out = (
            self.cfg.output_dir
            if self.cfg.output_dir
            else Path("output").resolve()
        )
        
        try:
            if self.simulator:
                self.simulator.simulate_ensure_dir(out)
            else:
                ensure_dir(out, False)
        except (OSError, PermissionError) as e:
            error(f"Cannot create output directory: {out}", e)
            return 2

        tmp_root = out / ".tmp_work"
        if self.simulator:
            self.simulator.simulate_create_temp_dir(tmp_root)
            tmp = tmp_root  # Use the path directly in dry run
            
            # Copy standalone mp4s
            copy_plans = self.planner.plan_copy_standalone_mp4s(
                input_folder, out
            )
            if copy_plans:
                self.simulator.simulate_copy_mp4s(copy_plans)

            # Unnamed files
            rename_input = self.planner.plan_unlabeled_renames(
                input_folder, out, out if out.is_relative_to(input_folder) else None
            )
            if rename_input:
                self.simulator.simulate_rename_files(rename_input)

            # Extract zips
            extract_plans = self.planner.plan_zip_extractions(
                input_folder, tmp
            )
            if extract_plans:
                self.simulator.simulate_extract_zips(extract_plans)

            # Unnamed in tmp and combine
            rename_tmp = self.planner.plan_unlabeled_renames(tmp, tmp)
            if rename_tmp:
                self.simulator.simulate_rename_files(rename_tmp)
            
            combine_plans = self.planner.plan_filesystem_combinations(tmp, out)

            # Combine
            if combine_plans:
                try:
                    img_done, vid_done = self.simulator.simulate_combine_files(
                        combine_plans,
                        self.cfg.image_workers,
                        self.cfg.video_workers,
                    )
                except Exception as e:
                    error("Failed to simulate combine files", e)
                    return 1

            # Metadata (optional)
            if self.cfg.metadata_html:
                if not self.cfg.metadata_html.exists():
                    warning(f"Metadata HTML file not found: {self.cfg.metadata_html}")
                else:
                    try:
                        img_tag, vid_tag = self.simulator.simulate_apply_metadata(
                            self.cfg.metadata_html, out
                        )
                        if img_tag > 0 or vid_tag > 0:
                            info(
                                f"🧭 Would apply metadata → images: {img_tag}, "
                                f"videos: {vid_tag}"
                            )
                    except Exception as e:
                        warning(f"Failed to simulate metadata: {e}")

            # Remove ZIP files after extraction
            zip_files = find_zip_files_top_level(input_folder)
            if zip_files:
                self.simulator.simulate_remove_zips(zip_files)
        else:
            try:
                with managed_tmp_dir(tmp_root, False) as tmp:
                    # Copy standalone mp4s
                    copy_plans = self.planner.plan_copy_standalone_mp4s(
                        input_folder, out
                    )
                    if copy_plans:
                        try:
                            _ = self.copier.run(copy_plans, False)
                        except Exception as e:
                            error("Failed to copy MP4 files", e)
                            return 1

                    # Unnamed files
                    rename_input = self.planner.plan_unlabeled_renames(
                        input_folder, out, out if out.is_relative_to(input_folder) else None
                    )
                    if rename_input:
                        try:
                            _ = self.renamer.run(rename_input, False)
                        except Exception as e:
                            error("Failed to rename files", e)
                            return 1

                    # Extract zips
                    extract_plans = self.planner.plan_zip_extractions(
                        input_folder, tmp
                    )
                    if extract_plans:
                        try:
                            _ = self.zips.run(extract_plans, False)
                        except Exception as e:
                            error("Failed to extract ZIP files", e)
                            return 1

                    # Unnamed in tmp and combine
                    rename_tmp = self.planner.plan_unlabeled_renames(tmp, tmp)
                    if rename_tmp:
                        try:
                            _ = self.renamer.run(rename_tmp, False)
                        except Exception as e:
                            error("Failed to rename files", e)
                            return 1
                    
                    combine_plans = self.planner.plan_filesystem_combinations(tmp, out)

                    # Combine
                    if combine_plans:
                        try:
                            img_done, vid_done = self.combiner.run(
                                combine_plans,
                                False,
                                self.cfg.image_workers,
                                self.cfg.video_workers,
                            )
                        except KeyboardInterrupt:
                            error("Processing interrupted by user")
                            return 130
                        except Exception as e:
                            error("Failed to combine files", e)
                            return 1

                    # Metadata (optional)
                    if self.cfg.metadata_html:
                        if not self.cfg.metadata_html.exists():
                            warning(f"Metadata HTML file not found: {self.cfg.metadata_html}")
                        else:
                            try:
                                meta = parse_memories_html(self.cfg.metadata_html)
                                info(f"🧭 Applying metadata ({len(meta)} entries found in HTML)...")
                                img_tag, vid_tag = apply_metadata_to_outputs(out, meta, self.cfg.metadata_workers)
                                info(
                                    f"🧭 Metadata applied → images: {img_tag}, "
                                    f"videos: {vid_tag}"
                                )
                            except Exception as e:
                                warning(f"Failed to apply metadata: {e}")

                    # Remove ZIP files after extraction
                    zip_files = find_zip_files_top_level(input_folder)
                    if zip_files:
                        removed_count = 0
                        for zip_file in zip_files:
                            try:
                                zip_file.unlink()
                                removed_count += 1
                            except Exception as e:
                                warning(f"Failed to remove ZIP file {zip_file.name}: {e}")
                        if removed_count > 0:
                            info(f"🗑️ ZIP files removed: {removed_count}")
            except Exception as e:
                error("Failed to process folder", e)
                return 1

        # Summary
        info("\n✅ Done." if not self.cfg.dry_run else "\n✅ Dry run complete.")
        info(f"📁 Output folder: {out}")
        try:
            z, n, m, total = count_input_breakdown(input_folder, out)
            info(
                f"⬆️ Input: {total} (zips: {z}, unnamed: {n}, mp4s: {m})"
            )
            if not self.cfg.dry_run:
                info(f"⬇️ Output Memories: {count_output_memories(out)}")
        except Exception as e:
            warning(f"Failed to generate summary statistics: {e}")
        return 0
