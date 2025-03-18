#!/usr/bin/env python3
import os
import subprocess
import sys
import shutil
import tempfile
import argparse
import json

def run_command(command, cwd=None, verbose=False):
    """Run a shell command and return the output"""
    if verbose and 'curl' in command:
        # Add verbose flag to curl commands
        command = command.replace('curl -s', 'curl -sv')
        print(f"Running command: {command}")
    
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            check=True, 
            text=True, 
            capture_output=True,
            cwd=cwd
        )
        if verbose:
            print(f"Command output: {result.stdout}")
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {command}")
        print(f"Error output: {e.stderr}")
        if 'curl' in command:
            # Try without check=True to get more info
            try:
                result = subprocess.run(
                    command, 
                    shell=True, 
                    text=True, 
                    capture_output=True,
                    cwd=cwd
                )
                print(f"Additional curl info - stdout: {result.stdout}")
                print(f"Additional curl info - stderr: {result.stderr}")
            except Exception:
                pass
        sys.exit(1)

def create_gitignore(repo_path):
    """Create or update .gitignore to exclude node_modules and other unnecessary files"""
    gitignore_path = os.path.join(repo_path, '.gitignore')
    
    # Check if .gitignore already exists
    if os.path.exists(gitignore_path):
        with open(gitignore_path, 'r') as f:
            content = f.read()
            
        # Check if node_modules is already in .gitignore
        if 'node_modules' not in content:
            with open(gitignore_path, 'a') as f:
                f.write('\n# Added by deployment script\nnode_modules/\n.next/\n')
    else:
        # Create new .gitignore
        with open(gitignore_path, 'w') as f:
            f.write('# Node.js\nnode_modules/\n.next/\n.env\nnpm-debug.log\nyarn-error.log\n')

def check_repo_exists(remote_url, token, verbose=True):
    """Check if the repository exists and is accessible"""
    try:
        # Extract owner and repo name from URL
        path = remote_url.replace('https://github.com/', '').replace('.git', '')
        parts = path.split('/')
        if len(parts) != 2:
            return False
        
        owner, repo_name = parts
        
        # Construct the API URL directly
        api_url = f"https://api.github.com/repos/{owner}/{repo_name}"
        
        if verbose:
            print(f"API URL: {api_url}")
            
        headers = f'Authorization: token {token}'
        command = f'curl -s -H "{headers}" {api_url}'
        result = run_command(command, verbose=verbose)
        return 'not found' not in result.lower() and 'bad credentials' not in result.lower()
    except Exception as e:
        if verbose:
            print(f"Error checking repo: {str(e)}")
        return False

def create_repo(remote_url, token, private=True, verbose=True):
    """Create a new repository on GitHub"""
    try:
        # Extract owner and repo name from URL
        path = remote_url.replace('https://github.com/', '').replace('.git', '')
        parts = path.split('/')
        if len(parts) != 2:
            return False
        
        owner, repo_name = parts
        
        # Create the repo using GitHub API
        api_url = "https://api.github.com/user/repos"
        
        if verbose:
            print(f"Create repo API URL: {api_url}")
            
        headers = f'Authorization: token {token}'
        data = json.dumps({
            "name": repo_name,
            "private": private,
            "auto_init": False
        })
        
        command = f'curl -s -X POST -H "Content-Type: application/json" -H "{headers}" -d \'{data}\' {api_url}'
        result = run_command(command, verbose=verbose)
        
        # Check if repo was created successfully
        return "full_name" in result
    except Exception as e:
        print(f"Error creating repository: {str(e)}")
        return False

def push_to_github(remote_url, token, branch='main', force=False, create_if_not_exists=True, private=True, verbose=True):
    """Push the current directory to GitHub using a token"""
    # Get the current directory
    current_path = os.getcwd()
    
    # Check if repository exists
    repo_exists = check_repo_exists(remote_url, token, verbose)
    
    if not repo_exists and create_if_not_exists:
        print(f"Repository does not exist. Attempting to create it...")
        repo_created = create_repo(remote_url, token, private, verbose)
        if repo_created:
            print(f"Repository created successfully!")
            repo_exists = True
        else:
            print(f"Could not create repository. Will attempt to push anyway...")
    
    # Create a temporary directory for the repo
    with tempfile.TemporaryDirectory() as tmp_dir:
        print(f"Created temporary directory: {tmp_dir}")
        
        # Copy all files except node_modules and .git
        print("Copying project files...")
        for item in os.listdir(current_path):
            if item in ['node_modules', '.git', '.next']:
                continue
                
            src_path = os.path.join(current_path, item)
            dst_path = os.path.join(tmp_dir, item)
            
            if os.path.isdir(src_path):
                shutil.copytree(src_path, dst_path)
            else:
                shutil.copy2(src_path, dst_path)
        
        # Ensure .gitignore exists and contains node_modules
        create_gitignore(tmp_dir)
        
        # Initialize git repo in the temporary directory
        print("Initializing Git repository...")
        run_command("git init", tmp_dir)
        
        # Configure Git user for commit
        print("Configuring Git user...")
        run_command('git config user.name "GitHub Push Script"', tmp_dir)
        run_command('git config user.email "no-reply@example.com"', tmp_dir)
        
        # Configure Git to use the token
        remote_with_token = remote_url.replace('https://', f'https://{token}@')
        
        # Add the remote
        run_command(f'git remote add origin {remote_with_token}', tmp_dir)
        
        # If repository exists and we're not forcing, try to pull first
        if repo_exists and not force:
            try:
                print(f"Repository exists. Attempting to fetch existing history...")
                run_command(f"git fetch origin {branch}", tmp_dir)
                run_command(f"git checkout -b {branch} origin/{branch}", tmp_dir)
                print("Successfully fetched existing history.")
            except Exception as e:
                print(f"Could not fetch history: {str(e)}")
                print("Continuing with fresh repository...")
        
        # Add all files
        print("Adding files to Git...")
        run_command("git add .", tmp_dir)
        
        # Commit
        print("Committing files...")
        commit_msg = "Update via deployment script" if repo_exists else "Initial commit via deployment script"
        run_command(f'git commit -m "{commit_msg}"', tmp_dir)
        
        # Create and checkout the branch explicitly
        print(f"Creating and checking out {branch} branch...")
        try:
            # Create branch if it doesn't exist
            run_command(f"git checkout -b {branch}", tmp_dir)
        except Exception as e:
            if verbose:
                print(f"Branch creation error (might already exist): {str(e)}")
            # Try to checkout the branch if it already exists
            try:
                run_command(f"git checkout {branch}", tmp_dir)
            except Exception as e:
                if verbose:
                    print(f"Branch checkout error: {str(e)}")
        
        # Push to GitHub
        force_flag = "--force" if force else ""
        print(f"Pushing to GitHub on branch {branch}{' (force)' if force else ''}...")
        push_command = f"git push -u origin {branch} {force_flag}"
        
        try:
            run_command(push_command, tmp_dir)
            print("Successfully pushed to GitHub!")
        except Exception as e:
            print(f"Push failed: {str(e)}")
            print("Trying alternative push method...")
            # Try an alternative push method
            try:
                alternative_push = f"git push --set-upstream origin {branch} {force_flag}"
                run_command(alternative_push, tmp_dir)
                print("Successfully pushed to GitHub using alternative method!")
            except Exception as e:
                print(f"Alternative push also failed: {str(e)}")
                raise e

def main():
    parser = argparse.ArgumentParser(description='Push a project to GitHub using a token')
    parser.add_argument('remote_url', help='GitHub repository URL (https://github.com/username/repo.git)')
    parser.add_argument('token', help='GitHub personal access token')
    parser.add_argument('--branch', default='main', help='Branch name to push to (default: main)')
    parser.add_argument('--force', action='store_true', help='Force push to repository (use with caution)')
    parser.add_argument('--create', action='store_true', help='Create the repository if it does not exist')
    parser.add_argument('--public', action='store_true', help='Make the repository public (default is private)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output for debugging')
    
    args = parser.parse_args()
    
    # Validate remote URL
    if not args.remote_url.startswith('https://github.com/'):
        print("Error: Remote URL must be in the format https://github.com/username/repo.git")
        sys.exit(1)
    
    # Ensure token is provided
    if not args.token:
        print("Error: GitHub token is required")
        sys.exit(1)
    
    push_to_github(
        args.remote_url, 
        args.token, 
        args.branch, 
        args.force,
        args.create,
        not args.public,
        args.verbose
    )

if __name__ == "__main__":
    main() 