# PyFlamegraph

A pure Python implementation of flamegraph generation tools. This project provides Python replacements for Brendan Gregg's original Perl-based flamegraph utilities, enabling performance profiling visualization without Perl dependencies.

## Overview

PyFlamegraph converts Linux `perf` profiling data into interactive flamegraph visualizations in SVG or PNG format. Flamegraphs are a visualization technique that helps identify hot code paths in software performance profiles.

## Components

### perf-flame.py

An all-in-one script that combines stack collapsing and flamegraph generation. It reads `perf script` output from stdin and produces either PNG or SVG flamegraph visualizations.

### stackcollapse_perf.py

A Python replacement for `stackcollapse-perf.pl`. This script parses the output of `perf script` and collapses identical call stacks, outputting them in the folded stack format (one line per unique stack with its sample count).

### flamegraph.py

A Python replacement for `flamegraph.pl`. This script reads folded stack data and generates PNG flamegraph visualizations.

## Requirements

- Python 3.6 or higher
- Optional: Pillow (PIL) for enhanced PNG generation with text labels

If Pillow is not installed, PNG generation will use a basic fallback method.

## Installation

Clone the repository:

```bash
git clone <repository-url>
cd PyFlamegraph
```

Optional: Install Pillow for better PNG output:

```bash
pip install Pillow
```

## Usage

### All-in-One (perf-flame.py)

Generate an SVG flamegraph:

```bash
perf script | python3 perf-flame.py --format svg > flamegraph.svg
```

Generate a PNG flamegraph:

```bash
perf script | python3 perf-flame.py --format png > flamegraph.png
```

Specify a custom title:

```bash
perf script | python3 perf-flame.py --format svg --title "My Application CPU Profile" > flamegraph.svg
```

### Two-Step Process

First, collapse the stacks:

```bash
perf script | python3 stackcollapse_perf.py > collapsed.txt
```

Then, generate the flamegraph:

```bash
cat collapsed.txt | python3 flamegraph.py > flamegraph.png
```

### Using with Recorded Perf Data

Record performance data:

```bash
perf record -g -F 99 ./your_application
```

Generate the flamegraph:

```bash
perf script | python3 perf-flame.py --format svg > flamegraph.svg
```

## Command Line Options

### perf-flame.py

| Option | Description | Default |
|--------|-------------|---------|
| `--format` | Output format: `png` or `svg` | `png` |
| `--title` | Title displayed on the flamegraph | `CPU Flame Graph` |

## Output Formats

### SVG

- Interactive and scalable
- Smaller file sizes for large profiles
- Viewable in any web browser
- Recommended for most use cases

### PNG

- Static image format
- Requires Pillow for full-featured output
- Useful for embedding in documents or presentations

## How It Works

1. **Stack Parsing**: The tool reads `perf script` output, which contains sampled call stacks from the profiled application.

2. **Stack Collapsing**: Identical call stacks are grouped and counted. Each unique stack trace becomes a single line with its occurrence count.

3. **Visualization**: The collapsed stacks are rendered as a flamegraph where:
   - The x-axis represents the proportion of samples
   - The y-axis shows the call stack depth
   - Each rectangle represents a function in the call stack
   - Wider rectangles indicate more time spent in that function
   - Colors are assigned based on function name hashing for consistency

## License

This project is licensed under the GNU General Public License v3.0. See the LICENSE file for details.

## Acknowledgments

This project is inspired by Brendan Gregg's original flamegraph tools:
- [FlameGraph](https://github.com/brendangregg/FlameGraph)

## Contributing

Contributions are welcome. Please ensure that any modifications maintain compatibility with the existing interface and follow Python best practices.

