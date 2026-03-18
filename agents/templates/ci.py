"""CI Workflow Templates for GitHub Actions"""

PYTHON_PYTEST_WORKFLOW = """name: CI

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '{python_version}'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install pytest pytest-cov
        if [ -f requirements.txt ]; then 
          pip install -r requirements.txt
        elif [ -f pyproject.toml ]; then
          if grep -q "tool.poetry" pyproject.toml; then
            pip install poetry
            poetry install --no-root || poetry install
          else
            pip install -e . || pip install .
          fi
        fi
        pip list
    
    - name: Run tests
      run: |
        export PYTHONPATH=$PYTHONPATH:$(pwd)
        if [ -d tests ]; then
            pytest tests/ --cov=. --cov-report=term-missing -v || pytest tests/ -v
        else
            echo "No tests directory found"
            exit 1
        fi
"""

PYTHON_UNITTEST_WORKFLOW = """name: CI

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '{python_version}'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        if [ -f requirements.txt ]; then 
          pip install -r requirements.txt
        elif [ -f pyproject.toml ]; then 
          pip install -e . || pip install .
        fi
        pip list
    
    - name: Run tests
      run: |
        export PYTHONPATH=$PYTHONPATH:$(pwd)
        if [ -d tests ]; then
          python -m unittest discover -s tests -p 'test_*.py' -v
        else
          echo "No tests directory found"
          exit 1
        fi
"""

JAVASCRIPT_JEST_WORKFLOW = """name: CI

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Node.js
      uses: actions/setup-node@v3
      with:
        node-version: '{node_version}'
    
    - name: Install dependencies
      run: |
        if [ -f package-lock.json ]; then
          npm ci
        elif [ -f yarn.lock ]; then
          yarn install --frozen-lockfile
        elif [ -f pnpm-lock.yaml ]; then
          npm install -g pnpm
          pnpm install --frozen-lockfile
        elif [ -f package.json ]; then
          npm install
        else
          echo "No package.json found"
          exit 1
        fi
    
    - name: Run tests
      run: npm test
"""

TYPESCRIPT_JEST_WORKFLOW = """name: CI

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Node.js
      uses: actions/setup-node@v3
      with:
        node-version: '{node_version}'
    
    - name: Install dependencies
      run: |
        if [ -f package-lock.json ]; then
          npm ci
        elif [ -f yarn.lock ]; then
          yarn install --frozen-lockfile
        elif [ -f package.json ]; then
          npm install
        fi
    
    - name: Build TypeScript
      run: |
        if [ -f tsconfig.json ]; then
          npm run build || npx tsc || echo "Build step skipped"
        fi
    
    - name: Run tests
      run: npm test
"""

GO_TEST_WORKFLOW = """name: CI

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Go
      uses: actions/setup-go@v4
      with:
        go-version: '{go_version}'
    
    - name: Install dependencies
      run: |
        if [ -f go.mod ]; then
          go mod download
          go mod verify
        fi
    
    - name: Build
      run: go build -v ./... || echo "Build step skipped"
    
    - name: Run tests
      run: go test -v -race -coverprofile=coverage.out ./...
"""

JAVA_JUNIT_WORKFLOW = """name: CI

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up JDK
      uses: actions/setup-java@v3
      with:
        java-version: '{java_version}'
        distribution: 'temurin'
    
    - name: Cache Maven packages
      uses: actions/cache@v3
      with:
        path: ~/.m2
        key: ${{ runner.os }}-m2-${{ hashFiles('**/pom.xml') }}
    
    - name: Build and Test
      run: |
        if [ -f pom.xml ]; then
          mvn clean test -B
        elif [ -f build.gradle ] || [ -f build.gradle.kts ]; then
          if [ -f gradlew ]; then
            chmod +x gradlew
            ./gradlew test --no-daemon
          else
            gradle test
          fi
        else
          echo "No Maven or Gradle build file found"
          exit 1
        fi
"""

RUST_CARGO_WORKFLOW = """name: CI

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Rust
      uses: actions-rs/toolchain@v1
      with:
        toolchain: stable
        override: true
    
    - name: Cache cargo
      uses: actions/cache@v3
      with:
        path: |
          ~/.cargo/registry
          ~/.cargo/git
          target
        key: ${{ runner.os }}-cargo-${{ hashFiles('**/Cargo.lock') }}
    
    - name: Build
      run: cargo build --verbose
    
    - name: Run tests
      run: cargo test --verbose
"""

RUBY_RSPEC_WORKFLOW = """name: CI

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Ruby
      uses: ruby/setup-ruby@v1
      with:
        ruby-version: '{ruby_version}'
        bundler-cache: true
    
    - name: Install dependencies
      run: |
        if [ -f Gemfile ]; then
          bundle install
        else
          gem install rspec
        fi
    
    - name: Run tests
      run: bundle exec rspec || rspec
"""

PHP_PHPUNIT_WORKFLOW = """name: CI

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up PHP
      uses: shivammathur/setup-php@v2
      with:
        php-version: '{php_version}'
        extensions: mbstring, xml, ctype, json
        coverage: xdebug
    
    - name: Install dependencies
      run: |
        if [ -f composer.json ]; then
          composer install --prefer-dist --no-progress
        else
          echo "No composer.json found"
          exit 1
        fi
    
    - name: Run tests
      run: vendor/bin/phpunit
"""

CSHARP_NUNIT_WORKFLOW = """name: CI

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up .NET
      uses: actions/setup-dotnet@v3
      with:
        dotnet-version: '7.0.x'
    
    - name: Restore dependencies
      run: dotnet restore
    
    - name: Build
      run: dotnet build --no-restore
    
    - name: Run tests
      run: dotnet test --no-build --verbosity normal
"""

CPP_CMAKE_WORKFLOW = """name: CI

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Install dependencies
      run: |
        sudo apt-get update
        sudo apt-get install -y cmake build-essential

    - name: Configure CMake
      run: cmake -B build -S .

    - name: Build
      run: cmake --build build

    - name: Test
      run: |
        cd build
        ctest --output-on-failure
"""

DEFAULT_WORKFLOW = """name: CI

on:
  push:
    branches: [ main, master ]
  pull_request:
    branches: [ main, master ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Check for test files
      run: |
        echo "Checking for test files..."
        find . -name "*test*" -type f || echo "No test files found"
    
    - name: Run tests
      run: |
        echo "No test framework configured for this language"
        echo "Please configure CI manually"
        exit 1
"""

# Workflow lookup table
WORKFLOW_TEMPLATES = {
    "Python": {
        "pytest": PYTHON_PYTEST_WORKFLOW,
        "unittest": PYTHON_UNITTEST_WORKFLOW,
    },
    "JavaScript": {
        "jest": JAVASCRIPT_JEST_WORKFLOW,
    },
    "TypeScript": {
        "jest": TYPESCRIPT_JEST_WORKFLOW,
    },
    "React/JavaScript": {
        "jest": JAVASCRIPT_JEST_WORKFLOW,
    },
    "React/TypeScript": {
        "jest": TYPESCRIPT_JEST_WORKFLOW,
    },
    "Go": {
        "go test": GO_TEST_WORKFLOW,
    },
    "Java": {
        "JUnit": JAVA_JUNIT_WORKFLOW,
    },
    "Rust": {
        "cargo test": RUST_CARGO_WORKFLOW,
    },
    "Ruby": {
        "RSpec": RUBY_RSPEC_WORKFLOW,
    },
    "PHP": {
        "PHPUnit": PHP_PHPUNIT_WORKFLOW,
    },
    "C#": {
        "NUnit": CSHARP_NUNIT_WORKFLOW,
    },
    "C++": {
        "Google Test": CPP_CMAKE_WORKFLOW,
        "generic": CPP_CMAKE_WORKFLOW,
    },
    "C": {
        "Unity": CPP_CMAKE_WORKFLOW,
        "generic": CPP_CMAKE_WORKFLOW,
    },
}


def get_workflow_content(language: str, test_framework: str, versions: dict = None) -> str:
    """Get CI workflow content for language and framework with optional version overrides"""
    template = WORKFLOW_TEMPLATES.get(language, {}).get(test_framework, DEFAULT_WORKFLOW)
    
    # Default versions if not provided
    defaults = {
        'python_version': '3.11',
        'node_version': '20',
        'go_version': '1.21',
        'java_version': '17',
        'ruby_version': '3.2',
        'php_version': '8.2',
        'dotnet_version': '7.0.x'
    }
    
    if versions:
        defaults.update(versions)
        
    try:
        if '{' in template and '}' in template:
            # Safer replacement than format() to avoid ${{ }} issues
            content = template
            for key, value in defaults.items():
                content = content.replace(f"{{{key}}}", str(value))
            return content
        return template
    except Exception:
        return template
