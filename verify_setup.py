#!/usr/bin/env python3
"""
Verification script for two-project GCP setup.
Checks that both credentials files exist and configuration is correct.
"""

import os
import json
import sys
from pathlib import Path

def check_file_exists(filepath, description):
    """Check if a file exists."""
    path = Path(filepath)
    if path.exists():
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ {description}: {filepath} (NOT FOUND)")
        return False

def check_credentials_project(filepath, expected_project, description):
    """Check if credentials file has correct project ID."""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        actual_project = data.get('project_id', 'UNKNOWN')
        
        if actual_project == expected_project:
            print(f"✅ {description}: {actual_project}")
            return True
        else:
            print(f"❌ {description}:")
            print(f"   Expected: {expected_project}")
            print(f"   Found: {actual_project}")
            return False
    except Exception as e:
        print(f"❌ {description}: Error reading file - {e}")
        return False

def check_env_variable(varname, expected_value=None):
    """Check if environment variable is set."""
    value = os.getenv(varname)
    
    if value:
        if expected_value and value != expected_value:
            print(f"⚠️  {varname}: {value} (expected: {expected_value})")
            return False
        else:
            print(f"✅ {varname}: {value}")
            return True
    else:
        print(f"❌ {varname}: NOT SET")
        return False

def load_env_file():
    """Load .env file into os.environ."""
    env_file = Path('.env')
    if not env_file.exists():
        print("❌ .env file not found in current directory!")
        return False
    
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if line and not line.startswith('#'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip('"').strip("'")
                    os.environ[key.strip()] = value
    
    print("✅ .env file loaded\n")
    return True

def main():
    """Run all verification checks."""
    
    print("=" * 70)
    print("LUMORA AI: GCP TWO-PROJECT SETUP VERIFICATION")
    print("=" * 70)
    print()
    
    # Change to backend directory
    backend_path = Path(__file__).parent
    os.chdir(backend_path)
    
    print(f"Working directory: {os.getcwd()}\n")
    
    # Load .env file
    if not load_env_file():
        return False
    
    # Track results
    all_good = True
    
    # ===== PHASE 1: Credentials Files
    print("=" * 70)
    print("PHASE 1: Credentials Files")
    print("=" * 70)
    print()
    
    # Check Firebase credentials
    if check_file_exists('firebase-credentials.json', 'Firebase Credentials File'):
        if not check_credentials_project('firebase-credentials.json', 'lumora-ai-58401', 
                                        'Firebase Project ID'):
            all_good = False
    else:
        all_good = False
    
    print()
    
    # Check Vertex AI credentials
    if check_file_exists('vertex-ai-credentials.json', 'Vertex AI Credentials File'):
        if not check_credentials_project('vertex-ai-credentials.json', 'project-e6d513b1-db45-4ab3-9a1',
                                        'Vertex AI Project ID'):
            all_good = False
    else:
        print("⚠️  Vertex AI credentials file not found - you need to download it first!")
        all_good = False
    
    print()
    
    # ===== PHASE 2: Environment Variables
    print("=" * 70)
    print("PHASE 2: Environment Variables")
    print("=" * 70)
    print()
    
    # Firebase Project
    print("Firebase Project:")
    check_env_variable('FIREBASE_PROJECT_ID', 'lumora-ai-58401')
    check_env_variable('FIREBASE_CREDENTIALS_PATH', './firebase-credentials.json')
    print()
    
    # Vertex AI Project
    print("Vertex AI Project:")
    check_env_variable('GOOGLE_CLOUD_PROJECT', 'project-e6d513b1-db45-4ab3-9a1')
    check_env_variable('GOOGLE_CLOUD_LOCATION', 'us-central1')
    check_env_variable('GOOGLE_APPLICATION_CREDENTIALS', './vertex-ai-credentials.json')
    print()
    
    # Video Generation
    print("Video Generation:")
    check_env_variable('VERTEX_VIDEO_MODEL', 'veo-3.1-fast-generate-001')
    check_env_variable('VERTEX_VIDEO_OUTPUT_GCS_URI', 'gs://project-e6d513b1-video-outputs/')
    check_env_variable('VERTEX_VIDEO_OUTPUT_DIR', './generated_videos')
    print()
    
    # Image Generation
    print("Image Generation:")
    check_env_variable('VERTEX_IMAGE_MODEL', 'imagen-3.0-generate-002')
    print()
    
    # GCS Bucket
    print("GCS Bucket:")
    check_env_variable('GCS_BUCKET_NAME', 'project-e6d513b1-video-outputs')
    print()
    
    # ===== PHASE 3: Directory Structure
    print("=" * 70)
    print("PHASE 3: Directory Structure")
    print("=" * 70)
    print()
    
    if check_file_exists('generated_videos', 'Video Output Directory (optional)'):
        pass
    else:
        print("   Note: Directory will be created automatically on first run")
    
    print()
    
    # ===== SUMMARY
    print("=" * 70)
    if all_good:
        print("✅ SETUP VERIFICATION SUCCESSFUL!")
        print("=" * 70)
        print("\nYou're ready to use video and image generation!")
        print("\nNext steps:")
        print("  1. Start your backend: python main.py")
        print("  2. Test video generation endpoint")
        print("  3. Check logs for any errors")
        return True
    else:
        print("❌ SETUP VERIFICATION FAILED!")
        print("=" * 70)
        print("\nPlease fix the issues above and try again.")
        print("\nCommon problems:")
        print("  • Missing credentials files - download from GCP Console")
        print("  • Wrong project IDs - check credentials file contents")
        print("  • Wrong .env values - update from template")
        print("\nSee ENV_TWO_PROJECTS_SETUP.md for detailed instructions.")
        return False

if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
