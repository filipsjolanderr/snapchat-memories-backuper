
import shutil
import tempfile
import unittest
from pathlib import Path
from snap_memories.config import AppConfig
from snap_memories.pipeline import Pipeline
from snap_memories.fs import find_zip_files_recursively

class TestFolderModeReproduction(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.input_dir = self.test_dir / "input"
        self.output_dir = self.test_dir / "output"
        self.input_dir.mkdir()
        self.output_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_folder_mode_ignores_images_and_recursive_zips(self):
        # Setup: Create a standalone image and a nested zip in input
        (self.input_dir / "standalone_image.jpg").touch()
        subdir = self.input_dir / "subdir"
        subdir.mkdir()
        (subdir / "nested.zip").touch()
        
        # Also create a standard memory pair to ensure pipeline runs at all
        (self.input_dir / "memory-main.mp4").touch()
        (self.input_dir / "memory-overlay.png").touch() # Invalid png but file exists

        cfg = AppConfig(
            input_path=self.input_dir,
            output_dir=self.output_dir,
            dry_run=False
        )
        pipeline = Pipeline(cfg)
        
        # Run pipeline
        pipeline.run_folder_mode(self.input_dir)

        # Verification
        # 1. Check if standalone image was copied
        copied_image = self.output_dir / "standalone_image.jpg"
        if not copied_image.exists():
            print("FAILURE: Standalone image was NOT copied.")
        else:
            print("SUCCESS: Standalone image was copied.")

        # 2. Check if nested zip was found (and extracted/handled - but for now just check if we can simply detect it with current fs tools or if pipeline handled it)
        # The pipeline should have extracted it. For this test, let's just assert on the logic we want to fix.
        # Since extraction requires valid zip, let's just check if the pipeline logic would even see it.
        # Actually, let's make a real zip so extraction doesn't fail if it tries.
        import zipfile
        with zipfile.ZipFile(subdir / "nested.zip", 'w') as z:
            z.writestr("content.txt", "data")
            
        # Run pipeline again now that zip is valid
        # We need to clean output first or allow overwrite? Pipeline usually handles it.
        # check if content.txt exists in tmp or extracted location? 
        # Current pipeline extracts to tmp. If we want to verify it was processed, 
        # we can check if the code path for zip extraction was hit for this file.
        # But simpler: check if find_zip_files_recursively finds it.
        
        zips = find_zip_files_recursively(self.input_dir)
        # It is EXPECTED to fail currently because it is top_level only
        if any(z.name == "nested.zip" for z in zips):
             print("SUCCESS: Nested zip found by find_zip_files_recursively.")
        else:
             print("FAILURE: Nested zip NOT found by find_zip_files_recursively.")

if __name__ == "__main__":
    unittest.main()
