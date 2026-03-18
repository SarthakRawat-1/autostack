from typing import Dict, Tuple, List, Optional
import os

def detect_language(code_files: Dict[str, str]) -> str:
    extensions = [path.split('.')[-1] for path in code_files.keys() if '.' in path]

    extension_counts: Dict[str, int] = {}
    for ext in extensions:
        extension_counts[ext] = extension_counts.get(ext, 0) + 1

    if not extension_counts:
        return "Unknown"
    
    most_common_ext = max(extension_counts, key=extension_counts.get)

    language_map = {
        'py': 'Python',
        'js': 'JavaScript',
        'ts': 'TypeScript',
        'jsx': 'React/JavaScript',
        'tsx': 'React/TypeScript',
        'java': 'Java',
        'go': 'Go',
        'rs': 'Rust',
        'rb': 'Ruby',
        'php': 'PHP',
        'cs': 'C#',
        'cpp': 'C++',
        'c': 'C',
        'swift': 'Swift',
        'kt': 'Kotlin',
        'scala': 'Scala',
        'md': 'Markdown',
        'json': 'JSON',
        'yml': 'YAML',
        'yaml': 'YAML',
        'html': 'HTML',
        'css': 'CSS',
        'sh': 'Shell',
    }
    
    return language_map.get(most_common_ext, 'Unknown')

def get_markdown_code_block_lang(language: str) -> str:
    return {
        'Python': 'python',
        'JavaScript': 'javascript',
        'TypeScript': 'typescript',
        'React/JavaScript': 'jsx',
        'React/TypeScript': 'tsx',
        'Java': 'java',
        'Go': 'go',
        'Rust': 'rust',
        'Ruby': 'ruby',
        'PHP': 'php',
        'C#': 'csharp',
        'C++': 'cpp',
        'C': 'c',
        'Swift': 'swift',
        'Kotlin': 'kotlin',
        'Scala': 'scala',
        'Shell': 'bash',
        'HTML': 'html',
        'CSS': 'css',
    }.get(language, 'text')

TEST_FRAMEWORK_MAP = {
    'Python': 'pytest',
    'JavaScript': 'jest',
    'TypeScript': 'jest',
    'React/JavaScript': 'jest',
    'React/TypeScript': 'jest',
    'Java': 'JUnit',
    'Go': 'go test',
    'Rust': 'cargo test',
    'Ruby': 'RSpec',
    'PHP': 'PHPUnit',
    'C#': 'NUnit',
    'C++': 'Google Test',
    'C': 'Unity',
    'Swift': 'XCTest',
    'Kotlin': 'JUnit',
    'Scala': 'ScalaTest',
    'Elixir': 'ExUnit',
    'Clojure': 'clojure.test',
}

def get_test_framework(language: str) -> str:
    return TEST_FRAMEWORK_MAP.get(language, 'generic')

def detect_language_and_framework(code_files: Dict[str, str]) -> Tuple[str, str]:
    language = detect_language(code_files)
    test_framework = get_test_framework(language)
    return language, test_framework

def extract_project_versions(code_files: Dict[str, str]) -> Dict[str, str]:
    """
    Extract runtime versions from config files for various languages.
    Returns a dict of versions like {'node_version': '18', 'python_version': '3.11'}
    """
    versions = {}
    
    # Node.js
    if 'package.json' in code_files:
        import json
        try:
            pkg = json.loads(code_files['package.json'])
            if 'engines' in pkg and 'node' in pkg['engines']:
                # Extract major version from strings like ">=18.0.0", "18.x", "^18.0.0"
                node_ver = pkg['engines']['node']
                import re
                match = re.search(r'(\d+)', node_ver)
                if match:
                    versions['node_version'] = match.group(1)
        except:
            pass
            
    # Python
    if 'pyproject.toml' in code_files:
        content = code_files['pyproject.toml']
        # Simple regex for poetry/standard python version
        import re
        match = re.search(r'python\s*=\s*[\"^=]*(\d+\.\d+)', content)
        if match:
            versions['python_version'] = match.group(1)
    elif '.python-version' in code_files:
        versions['python_version'] = code_files['.python-version'].strip()
        
    # Go
    if 'go.mod' in code_files:
        import re
        match = re.search(r'go\s+(\d+\.\d+)', code_files['go.mod'])
        if match:
            versions['go_version'] = match.group(1)
            
    # Java (Maven)
    if 'pom.xml' in code_files:
        import re
        match = re.search(r'<java\.version>(\d+)</java\.version>', code_files['pom.xml'])
        if match:
            versions['java_version'] = match.group(1)
        # Also check maven.compiler.source
        elif re.search(r'<maven\.compiler\.source>(\d+)</maven\.compiler\.source>', code_files['pom.xml']):
            versions['java_version'] = re.search(r'<maven\.compiler\.source>(\d+)</maven\.compiler\.source>', code_files['pom.xml']).group(1)

    # Ruby
    if '.ruby-version' in code_files:
        versions['ruby_version'] = code_files['.ruby-version'].strip()
    elif 'Gemfile' in code_files:
        import re
        match = re.search(r"ruby\s+['\"]([^'\"]+)['\"]", code_files['Gemfile'])
        if match:
            versions['ruby_version'] = match.group(1)

    # PHP
    if 'composer.json' in code_files:
        import json
        try:
            composer = json.loads(code_files['composer.json'])
            require = composer.get('require', {})
            php_ver = require.get('php', '8.2')
            import re
            match = re.search(r'(\d+\.\d+)', php_ver)
            if match:
                versions['php_version'] = match.group(1)
        except:
            pass

    return versions
