#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to get current version from pyproject.toml
get_current_version() {
    grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/'
}

# Function to update version in pyproject.toml
update_version() {
    local new_version=$1
    sed -i.bak "s/^version = \".*\"/version = \"$new_version\"/" pyproject.toml
    rm -f pyproject.toml.bak
    print_success "Updated version to $new_version in pyproject.toml"
}

# Function to validate version format
validate_version() {
    if [[ ! $1 =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        print_error "Invalid version format: $1. Use semantic versioning (e.g., 1.2.3)"
        exit 1
    fi
}

# Function to check if working directory is clean
check_clean_working_dir() {
    if [[ -n $(git status --porcelain) ]]; then
        print_error "Working directory is not clean. Please commit or stash changes first."
        git status --short
        exit 1
    fi
    print_success "Working directory is clean"
}

# Function to run tests
run_tests() {
    print_status "Running tests..."
    if pytest -q --cov=fastmdanalysis --cov-report=term-missing; then
        print_success "All tests passed"
    else
        print_error "Tests failed. Fix issues before releasing."
        exit 1
    fi
}

# Function to create and push tag
create_release_tag() {
    local version=$1
    local message=$2
    
    print_status "Creating annotated tag v$version..."
    git tag -a "v$version" -m "$message"
    
    print_status "Pushing tag to GitHub..."
    git push origin "v$version"
    
    print_success "Tag v$version created and pushed"
}

# Function to generate changelog (basic)
generate_changelog() {
    local previous_tag=$1
    local new_version=$2
    
    print_status "Generating changelog since $previous_tag..."
    
    if git rev-parse "$previous_tag" >/dev/null 2>&1; then
        echo "## Changes since $previous_tag"
        echo ""
        git log --pretty=format:"- %s" "${previous_tag}..HEAD" | grep -v "Merge pull request" | grep -v "Merge branch"
    else
        echo "## Initial release"
    fi
}

# Main release function
release() {
    local new_version=$1
    local release_notes=$2
    
    print_status "Starting release process for v$new_version..."
    
    # Validate inputs
    if [[ -z "$new_version" ]]; then
        print_error "Version number required. Usage: ./release.sh <version> [release_notes]"
        exit 1
    fi
    
    validate_version "$new_version"
    
    # Get current version
    local current_version=$(get_current_version)
    print_status "Current version: $current_version"
    print_status "New version: $new_version"
    
    # Check if version is actually changing
    if [[ "$current_version" == "$new_version" ]]; then
        print_warning "Version is already $new_version. Did you forget to update it?"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    # Check working directory
    check_clean_working_dir
    
    # Update version
    update_version "$new_version"
    
    # Generate default release notes if not provided
    if [[ -z "$release_notes" ]]; then
        local previous_tag="v$current_version"
        release_notes="FastMDAnalysis v$new_version\n\n$(generate_changelog "$previous_tag" "$new_version")"
    fi
    
    # Commit version bump
    print_status "Committing version bump..."
    git add pyproject.toml
    git commit -m "bump: version $new_version"
    
    # Push to main
    print_status "Pushing to main branch..."
    git push origin main
    
    # Run tests (optional but recommended)
    read -p "Run tests before releasing? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        run_tests
    fi
    
    # Create and push release tag
    create_release_tag "$new_version" "$release_notes"
    
    print_success "🎉 Release process started for v$new_version!"
    echo ""
    print_status "Next steps:"
    echo "  1. Watch GitHub Actions: https://github.com/aai-research-lab/FastMDAnalysis/actions"
    echo "  2. Verify release: https://pypi.org/project/fastmdanalysis/"
    echo "  3. Check release: https://github.com/aai-research-lab/FastMDAnalysis/releases"
}

# Quick release function (minimal interaction)
quick_release() {
    local new_version=$1
    
    if [[ -z "$new_version" ]]; then
        print_error "Version number required. Usage: ./release.sh quick <version>"
        exit 1
    fi
    
    validate_version "$new_version"
    
    local current_version=$(get_current_version)
    local release_notes="FastMDAnalysis v$new_version\n\n## Changes\n- Bug fixes and improvements"
    
    print_status "Quick release for v$new_version..."
    
    update_version "$new_version"
    git add pyproject.toml
    git commit -m "bump: version $new_version"
    git push origin main
    create_release_tag "$new_version" "$release_notes"
    
    print_success "🚀 Quick release completed for v$new_version!"
}

# Show usage
usage() {
    echo "FastMDAnalysis Release Script"
    echo ""
    echo "Usage:"
    echo "  ./release.sh <version> [release_notes]  # Full release process"
    echo "  ./release.sh quick <version>            # Quick release (minimal interaction)"
    echo "  ./release.sh next                       # Auto-increment patch version"
    echo "  ./release.sh current                    # Show current version"
    echo ""
    echo "Examples:"
    echo "  ./release.sh 0.0.3"
    echo "  ./release.sh 1.0.0 \"Major release with new features\""
    echo "  ./release.sh quick 0.0.4"
    echo "  ./release.sh next"
}

# Auto-increment patch version
next_version() {
    local current_version=$(get_current_version)
    local major=$(echo $current_version | cut -d. -f1)
    local minor=$(echo $current_version | cut -d. -f2)
    local patch=$(echo $current_version | cut -d. -f3)
    
    local new_patch=$((patch + 1))
    local new_version="$major.$minor.$new_patch"
    
    print_status "Auto-incrementing version: $current_version → $new_version"
    release "$new_version"
}

# Show current version
show_current_version() {
    local current_version=$(get_current_version)
    print_status "Current version: $current_version"
}

# Main script logic
case "${1:-}" in
    ""|"-h"|"--help")
        usage
        ;;
    "current")
        show_current_version
        ;;
    "next")
        next_version
        ;;
    "quick")
        quick_release "$2"
        ;;
    *)
        release "$1" "$2"
        ;;
esac
