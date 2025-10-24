# High-Throughput Analysis of HSP90 Conformational Landscapes

**A FastMDAnalysis Tutorial**

This Case Study demonstrates how to use FastMDAnalysis for analyzing multiple molecular dynamics trajectories to identify conformational states across different replicates.

## Learning Objectives

By the end of this tutorial, you will be able to:
- Analyze multiple MD trajectories using FastMDAnalysis
- Identify metastable conformational states across replicates
- Perform collective analysis to find common states
- Generate reproducible, publication-ready results

## Prerequisites

- Basic knowledge of Python and molecular dynamics
- FastMDAnalysis installed (`pip install fastmdanalysis`)
- Basic familiarity with Jupyter notebooks

## 1. Introduction to the Case Study

We'll be analyzing simulated trajectories of the HSP90 N-terminal domain, a molecular chaperone that samples multiple conformational states. In a real scenario, you would have multiple independent MD replicates.

For this tutorial, we'll use example datasets to demonstrate the workflow.

## 2. Setting Up the Analysis Environment

```python
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
import json
from pathlib import Path

# FastMDAnalysis imports
from FastMDAnalysis import FastMDAnalysis
from FastMDAnalysis.datasets import example_datasets

# Set up plotting style
plt.style.use('default')
sns.set_palette("husl")
print("FastMDAnalysis tutorial: HSP90 Conformational Analysis")

def setup_analysis_directories():
    """Create organized directory structure for our analysis"""
    directories = [
        'hsp90_tutorial/individual_replicates',
        'hsp90_tutorial/collective_analysis', 
        'hsp90_tutorial/representative_structures',
        'hsp90_tutorial/figures'
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {directory}")
    
    return directories

# Create directory structure
directories = setup_analysis_directories()

```

## 3. Analyzing Individual Replicates
Let's start by analyzing each trajectory replicate individually. We'll compute:

- Root Mean Square Deviation (RMSD)
- Radius of Gyration (Rg)
- Secondary Structure
- Conformational clustering

```python
def analyze_single_replicate(traj_data, replicate_id, output_dir):
    """
    Analyze a single trajectory using FastMDAnalysis
    
    Parameters:
    traj_data: Dictionary containing 'trajectory' and 'topology' paths
    replicate_id: Identifier for this replicate
    output_dir: Directory to save results
    """
    
    print(f"\n Analyzing replicate: {replicate_id}")
    print("-" * 50)
    
    # Initialize FastMDAnalysis
    fmda = FastMDAnalysis(
        traj_file=traj_data['trajectory'],
        top_file=traj_data['topology'],
        atoms="protein and name CA",  # Focus on backbone
        frames=(0, -1, 5)  # Analyze every 5th frame for efficiency
    )
    
    print(f"Trajectory info: {len(fmda.traj)} frames")
    print(f"Topology info: {fmda.traj.n_residues} residues")
    
    # 3.1 Calculate basic structural metrics
    print(" Calculating structural metrics...")
    rmsd_result = fmda.rmsd(reference_frame=0)
    rg_result = fmda.rg()
    rmsf_result = fmda.rmsf()
    
    # 3.2 Analyze secondary structure
    print(" Analyzing secondary structure...")
    ss_result = fmda.ss()
    
    # 3.3 Dimensionality reduction for visualization
    print(" Performing dimensionality reduction...")
    embedding = fmda.dimred(
        methods=['pca', 'tsne'],
        n_components=2,
        tsne_perplexity=30
    )
    
    # 3.4 Identify conformational states through clustering
    print(" Clustering conformational states...")
    clusters = fmda.cluster(
        methods=['dbscan'],
        eps=0.2,
        min_samples=10,
        features='rmsd'
    )
    
    # Save results
    replicate_results = {
        'replicate_id': replicate_id,
        'structural_metrics': {
            'rmsd_mean': float(np.mean(rmsd_result.data)),
            'rmsd_std': float(np.std(rmsd_result.data)),
            'rg_mean': float(np.mean(rg_result.data)),
            'rg_std': float(np.std(rg_result.data)),
        },
        'clustering': {
            'n_clusters': len(np.unique(clusters.labels[clusters.labels >= 0])),
            'cluster_populations': np.bincount(clusters.labels[clusters.labels >= 0]).tolist(),
            'noise_points': np.sum(clusters.labels == -1)
        },
        'secondary_structure': {
            'helix_fraction': float(np.mean(ss_result.data == 'H')),
            'sheet_fraction': float(np.mean(ss_result.data == 'E')),
            'coil_fraction': float(np.mean(ss_result.data == 'C'))
        }
    }
    
    # Generate and save plots
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle(f'HSP90 Analysis - {replicate_id}', fontsize=16)
    
    # RMSD plot
    axes[0,0].plot(rmsd_result.data)
    axes[0,0].set_title('RMSD Evolution')
    axes[0,0].set_ylabel('RMSD (nm)')
    axes[0,0].set_xlabel('Frame')
    
    # Radius of gyration plot
    axes[0,1].plot(rg_result.data)
    axes[0,1].set_title('Radius of Gyration')
    axes[0,1].set_ylabel('Rg (nm)')
    axes[0,1].set_xlabel('Frame')
    
    # t-SNE visualization
    tsne_embedding = embedding.embeddings['tsne']
    scatter = axes[1,0].scatter(tsne_embedding[:, 0], tsne_embedding[:, 1], 
                               c=clusters.labels, cmap='viridis', alpha=0.6)
    axes[1,0].set_title('t-SNE Projection')
    axes[1,0].set_xlabel('t-SNE 1')
    axes[1,0].set_ylabel('t-SNE 2')
    plt.colorbar(scatter, ax=axes[1,0], label='Cluster')
    
    # Secondary structure composition
    ss_composition = [replicate_results['secondary_structure']['helix_fraction'],
                     replicate_results['secondary_structure']['sheet_fraction'], 
                     replicate_results['secondary_structure']['coil_fraction']]
    axes[1,1].bar(['Helix', 'Sheet', 'Coil'], ss_composition)
    axes[1,1].set_title('Secondary Structure Composition')
    axes[1,1].set_ylabel('Fraction')
    
    plt.tight_layout()
    plt.savefig(f'{output_dir}/{replicate_id}_analysis.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    # Save numerical results
    with open(f'{output_dir}/{replicate_id}_results.json', 'w') as f:
        json.dump(replicate_results, f, indent=2)
    
    print(f"Analysis complete for {replicate_id}")
    print(f"   - Found {replicate_results['clustering']['n_clusters']} clusters")
    print(f"   - Average RMSD: {replicate_results['structural_metrics']['rmsd_mean']:.3f} ± {replicate_results['structural_metrics']['rmsd_std']:.3f} nm")
    print(f"   - Helix content: {replicate_results['secondary_structure']['helix_fraction']:.2%}")
    
    return replicate_results, fmda, clusters, embedding
```

## 4. High-Throughput Analysis of Multiple Replicates
Now let's simulate analyzing multiple independent trajectories. In practice, you would load your actual trajectory files.

```python
# For this tutorial, we'll create simulated replicate data
# In real usage, replace this with your actual trajectory files

def create_simulated_replicates(n_replicates=5):
    """Create simulated dataset for tutorial purposes"""
    replicates = {}
    
    for i in range(n_replicates):
        rep_id = f"rep_{i+1:02d}"
        # In practice, you would use actual file paths:
        # replicates[rep_id] = {
        #     'trajectory': f'path/to/your/hsp90_rep{i+1}.dcd',
        #     'topology': 'path/to/your/hsp90_top.pdb'
        # }
        
        # For tutorial, we'll use example datasets
        if i % 2 == 0:
            # Use ubiquitin for half the replicates
            replicates[rep_id] = {
                'trajectory': example_datasets.ubiquitin.traj,
                'topology': example_datasets.ubiquitin.top
            }
        else:
            # Use trpcage for the other half
            replicates[rep_id] = {
                'trajectory': example_datasets.trpcage.traj,
                'topology': example_datasets.trpcage.top
            }
    
    return replicates

# Create simulated dataset
replicates = create_simulated_replicates(n_replicates=5)
print(f"Created {len(replicates)} simulated replicates for analysis")

# Analyze each replicate
all_results = {}
for rep_id, traj_data in replicates.items():
    results, fmda, clusters, embedding = analyze_single_replicate(
        traj_data, rep_id, 'hsp90_tutorial/individual_replicates'
    )
    all_results[rep_id] = results
```

## 5. Collective Analysis Across All Replicates
Now we'll combine data from all replicates to identify global conformational states.

```python
def perform_collective_analysis(all_results, output_dir):
    """Analyze data across all replicates to find global patterns"""
    
    print("\n PERFORMING COLLECTIVE ANALYSIS")
    print("=" * 50)
    
    # Aggregate key metrics
    rmsd_means = [results['structural_metrics']['rmsd_mean'] for results in all_results.values()]
    rg_means = [results['structural_metrics']['rg_mean'] for results in all_results.values()]
    helix_fractions = [results['secondary_structure']['helix_fraction'] for results in all_results.values()]
    n_clusters = [results['clustering']['n_clusters'] for results in all_results.values()]
    
    # Create summary visualization
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle('Collective Analysis Across All Replicates', fontsize=16)
    
    # RMSD distribution
    axes[0,0].bar(range(len(rmsd_means)), rmsd_means)
    axes[0,0].set_title('Average RMSD by Replicate')
    axes[0,0].set_ylabel('RMSD (nm)')
    axes[0,0].set_xlabel('Replicate')
    
    # Radius of gyration distribution
    axes[0,1].bar(range(len(rg_means)), rg_means)
    axes[0,1].set_title('Average Radius of Gyration by Replicate')
    axes[0,1].set_ylabel('Rg (nm)')
    axes[0,1].set_xlabel('Replicate')
    
    # Secondary structure comparison
    replicate_names = list(all_results.keys())
    helix_data = [results['secondary_structure']['helix_fraction'] for results in all_results.values()]
    sheet_data = [results['secondary_structure']['sheet_fraction'] for results in all_results.values()]
    coil_data = [results['secondary_structure']['coil_fraction'] for results in all_results.values()]
    
    x = np.arange(len(replicate_names))
    width = 0.25
    
    axes[1,0].bar(x - width, helix_data, width, label='Helix', alpha=0.8)
    axes[1,0].bar(x, sheet_data, width, label='Sheet', alpha=0.8)
    axes[1,0].bar(x + width, coil_data, width, label='Coil', alpha=0.8)
    axes[1,0].set_title('Secondary Structure by Replicate')
    axes[1,0].set_ylabel('Fraction')
    axes[1,0].set_xlabel('Replicate')
    axes[1,0].set_xticks(x)
    axes[1,0].set_xticklabels(replicate_names, rotation=45)
    axes[1,0].legend()
    
    # Cluster count distribution
    axes[1,1].bar(range(len(n_clusters)), n_clusters)
    axes[1,1].set_title('Number of Clusters by Replicate')
    axes[1,1].set_ylabel('Number of Clusters')
    axes[1,1].set_xlabel('Replicate')
    
    plt.tight_layout()
    plt.savefig(f'{output_dir}/collective_analysis.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    # Perform statistical analysis
    collective_stats = {
        'total_replicates': len(all_results),
        'rmsd_statistics': {
            'mean': float(np.mean(rmsd_means)),
            'std': float(np.std(rmsd_means)),
            'cv': float(np.std(rmsd_means) / np.mean(rmsd_means))
        },
        'rg_statistics': {
            'mean': float(np.mean(rg_means)),
            'std': float(np.std(rg_means)),
            'cv': float(np.std(rg_means) / np.mean(rg_means))
        },
        'secondary_structure_stats': {
            'mean_helix': float(np.mean(helix_fractions)),
            'mean_sheet': float(np.mean(sheet_data)),
            'mean_coil': float(np.mean(coil_data))
        },
        'clustering_summary': {
            'total_clusters_identified': sum(n_clusters),
            'mean_clusters_per_replicate': float(np.mean(n_clusters)),
            'replicates_with_multiple_states': sum(1 for n in n_clusters if n > 1)
        }
    }
    
    # Save collective statistics
    with open(f'{output_dir}/collective_statistics.json', 'w') as f:
        json.dump(collective_stats, f, indent=2)
    
    print(" Collective Analysis Results:")
    print(f"   - Total replicates analyzed: {collective_stats['total_replicates']}")
    print(f"   - Average RMSD: {collective_stats['rmsd_statistics']['mean']:.3f} ± {collective_stats['rmsd_statistics']['std']:.3f} nm")
    print(f"   - Average helix content: {collective_stats['secondary_structure_stats']['mean_helix']:.2%}")
    print(f"   - Replicates with multiple states: {collective_stats['clustering_summary']['replicates_with_multiple_states']}")
    
    return collective_stats

# Perform collective analysis
collective_stats = perform_collective_analysis(all_results, 'hsp90_tutorial/collective_analysis')
```

## 6. State Identification and Characterization
Let's identify the major conformational states and characterize their properties.

```python
def identify_global_states(all_results):
    """Identify and characterize global conformational states"""
    
    print("\n IDENTIFYING GLOBAL CONFORMATIONAL STATES")
    print("=" * 50)
    
    # Group replicates by their properties to identify common states
    high_helix_reps = []
    low_helix_reps = []
    compact_reps = []
    extended_reps = []
    
    for rep_id, results in all_results.items():
        helix_frac = results['secondary_structure']['helix_fraction']
        rg_value = results['structural_metrics']['rg_mean']
        
        if helix_frac > 0.3:  # Threshold for "high helix"
            high_helix_reps.append(rep_id)
        else:
            low_helix_reps.append(rep_id)
            
        if rg_value < 1.5:  # Threshold for "compact" (adjust based on your system)
            compact_reps.append(rep_id)
        else:
            extended_reps.append(rep_id)
    
    global_states = {
        'high_helix_state': {
            'replicates': high_helix_reps,
            'description': 'State with high helical content',
            'n_replicates': len(high_helix_reps)
        },
        'low_helix_state': {
            'replicates': low_helix_reps,
            'description': 'State with low helical content',
            'n_replicates': len(low_helix_reps)
        },
        'compact_state': {
            'replicates': compact_reps,
            'description': 'Compact conformational state',
            'n_replicates': len(compact_reps)
        },
        'extended_state': {
            'replicates': extended_reps,
            'description': 'Extended conformational state', 
            'n_replicates': len(extended_reps)
        }
    }
    
    # Visualize state distribution
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    
    # Helix-based states
    helix_counts = [len(high_helix_reps), len(low_helix_reps)]
    ax1.bar(['High Helix', 'Low Helix'], helix_counts)
    ax1.set_title('States by Helical Content')
    ax1.set_ylabel('Number of Replicates')
    
    # Compactness-based states
    compact_counts = [len(compact_reps), len(extended_reps)]
    ax2.bar(['Compact', 'Extended'], compact_counts)
    ax2.set_title('States by Compactness')
    ax2.set_ylabel('Number of Replicates')
    
    plt.tight_layout()
    plt.savefig('hsp90_tutorial/figures/global_states.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    print(" Global State Analysis:")
    for state_name, state_info in global_states.items():
        print(f"   - {state_name}: {state_info['n_replicates']} replicates")
        print(f"     {state_info['description']}")
    
    return global_states

# Identify global states
global_states = identify_global_states(all_results)
```

## 7. Generating the Final Report
Let's compile all our findings into a comprehensive report.

```python
def generate_final_report(all_results, collective_stats, global_states):
    """Generate a comprehensive final report"""
    
    print("\n GENERATING FINAL ANALYSIS REPORT")
    print("=" * 50)
    
    report = {
        'analysis_metadata': {
            'analysis_date': np.datetime64('today').astype(str),
            'software_used': 'FastMDAnalysis',
            'total_replicates_analyzed': len(all_results)
        },
        'executive_summary': {
            'key_finding': f"Identified {len(global_states)} major conformational states across {len(all_results)} replicates",
            'state_heterogeneity': f"{collective_stats['clustering_summary']['replicates_with_multiple_states']} replicates showed multiple conformational states",
            'structural_variability': f"RMSD variability (CV): {collective_stats['rmsd_statistics']['cv']:.3f}"
        },
        'detailed_findings': {
            'structural_properties': collective_stats['rmsd_statistics'],
            'secondary_structure': collective_stats['secondary_structure_stats'],
            'clustering_analysis': collective_stats['clustering_summary']
        },
        'conformational_states': global_states,
        'replicate_details': all_results
    }
    
    # Save comprehensive report
    with open('hsp90_tutorial/final_analysis_report.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    # Generate summary markdown report
    markdown_report = f"""
# HSP90 Conformational Analysis Report

## Executive Summary

- **Total Replicates Analyzed**: {report['analysis_metadata']['total_replicates_analyzed']}
- **Major Finding**: {report['executive_summary']['key_finding']}
- **State Heterogeneity**: {report['executive_summary']['state_heterogeneity']}
- **Structural Variability**: {report['executive_summary']['structural_variability']}

## Key Metrics

### Structural Properties
- Average RMSD: {report['detailed_findings']['structural_properties']['mean']:.3f} ± {report['detailed_findings']['structural_properties']['std']:.3f} nm
- Radius of Gyration: {collective_stats['rg_statistics']['mean']:.3f} ± {collective_stats['rg_statistics']['std']:.3f} nm

### Secondary Structure
- Average Helix Content: {report['detailed_findings']['secondary_structure']['mean_helix']:.2%}
- Average Sheet Content: {report['detailed_findings']['secondary_structure']['mean_sheet']:.2%}
- Average Coil Content: {report['detailed_findings']['secondary_structure']['mean_coil']:.2%}

### Conformational States Identified
"""
    
    for state_name, state_info in global_states.items():
        markdown_report += f"- **{state_name}**: {state_info['n_replicates']} replicates - {state_info['description']}\n"
    
    # Save markdown report
    with open('hsp90_tutorial/analysis_report.md', 'w') as f:
        f.write(markdown_report)
    
    print(" Final Report Generated!")
    print("   - JSON report: hsp90_tutorial/final_analysis_report.json")
    print("   - Markdown report: hsp90_tutorial/analysis_report.md")
    print("   - All individual analyses saved in subdirectories")
    
    return report

# Generate final report
final_report = generate_final_report(all_results, collective_stats, global_states)
```

## 8. Reproducibility and Logging
FastMDAnalysis automatically generates detailed logs for reproducibility.

```python
def demonstrate_reproducibility():
    """Demonstrate the reproducibility features of FastMDAnalysis"""
    
    print("\n🔒 REPRODUCIBILITY FEATURES")
    print("=" * 50)
    
    # Check for generated log files
    log_files = list(Path('hsp90_tutorial').rglob('*.log'))
    json_files = list(Path('hsp90_tutorial').rglob('*.json'))
    
    print("Generated files for reproducibility:")
    print(f"  - Log files: {len(log_files)}")
    print(f"  - JSON metadata files: {len(json_files)}")
    
    # Show example of logged parameters
    if json_files:
        example_file = json_files[0]
        with open(example_file, 'r') as f:
            example_data = json.load(f)
        
        print(f"\nExample metadata from {example_file.name}:")
        if 'replicate_id' in example_data:
            print(f"  - Replicate: {example_data['replicate_id']}")
        if 'structural_metrics' in example_data:
            print(f"  - RMSD mean: {example_data['structural_metrics']['rmsd_mean']:.3f}")
    
    print("\n Complete analysis archive saved in: hsp90_tutorial/")
    print("   All parameters, results, and logs are preserved for future reference")

# Demonstrate reproducibility
demonstrate_reproducibility()
```

## 9. Summary and Next Steps

### What We Accomplished:
- Analyzed multiple MD trajectories using FastMDAnalysis
- Identified conformational states across replicates
- Performed collective analysis to find global patterns
- Generated reproducible results with comprehensive logging
- Created publication-ready figures and reports

### Applying to Your Own Data:
To use this workflow with your own data:

```python
# Replace the simulated replicates with your actual data
your_replicates = {
    'rep_01': {
        'trajectory': 'path/to/your/trajectory1.dcd',
        'topology': 'path/to/your/topology.pdb'
    },
    'rep_02': {
        'trajectory': 'path/to/your/trajectory2.dcd', 
        'topology': 'path/to/your/topology.pdb'
    },
    # ... add more replicates
}
```

### Further Analysis Ideas:
- Add more sophisticated clustering methods
- Include contact analysis or pocket detection
- Integrate with experimental data validation
- Perform free energy calculations on identified states

```python
print("\n TUTORIAL COMPLETE!")
print("=" * 50)
print("You have successfully completed the HSP90 conformational analysis tutorial.")
print("\nNext steps:")
print("1. Review the generated reports in the 'hsp90_tutorial' directory")
print("2. Apply this workflow to your own MD trajectories")
print("3. Explore additional analysis modules in FastMDAnalysis")
print("\nFor more information, visit:")
print(" Documentation: https://github.com/aai-research-lab/fastmdanalysis")
print(" Issue tracker: https://github.com/aai-research-lab/fastmdanalysis/issues")
```

### Repository Information
This tutorial is part of the FastMDAnalysis package. For more information, visit:

- Documentation: https://github.com/aai-research-lab/fastmdanalysis
- Issue Tracker: https://github.com/aai-research-lab/fastmdanalysis/issues
- Installation:
  ```bash
  pip install fastmdanalysis
  ```


