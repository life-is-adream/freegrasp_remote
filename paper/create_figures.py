"""Create figures for the RAL paper."""

import matplotlib.pyplot as plt
import numpy as np

# Set style
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.size'] = 12
plt.rcParams['font.family'] = 'serif'


def create_main_results_figure():
    """Create main results comparison bar chart."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))

    # Data
    methods = ['ThinkGrasp', 'FreeGrasp', 'FreeGrasp++']
    easy_rsr = [63.0, 83.0, 84.0]
    medium_rsr = [13.0, 46.0, 53.0]
    hard_rsr = [5.0, 22.0, 29.0]

    easy_ssr = [46.0, 64.0, 79.0]
    medium_ssr = [16.0, 40.0, 60.0]
    hard_ssr = [15.0, 13.0, 34.0]

    x = np.arange(len(methods))
    width = 0.25

    # RSR plot
    ax1.bar(x - width, easy_rsr, width, label='Easy', color='#2ecc71')
    ax1.bar(x, medium_rsr, width, label='Medium', color='#f39c12')
    ax1.bar(x + width, hard_rsr, width, label='Hard', color='#e74c3c')
    ax1.set_ylabel('RSR (%)')
    ax1.set_title('Reasoning Success Rate')
    ax1.set_xticks(x)
    ax1.set_xticklabels(methods)
    ax1.legend()
    ax1.set_ylim(0, 100)

    # SSR plot
    ax2.bar(x - width, easy_ssr, width, label='Easy', color='#2ecc71')
    ax2.bar(x, medium_ssr, width, label='Medium', color='#f39c12')
    ax2.bar(x + width, hard_ssr, width, label='Hard', color='#e74c3c')
    ax2.set_ylabel('SSR (%)')
    ax2.set_title('Segmentation Success Rate')
    ax2.set_xticks(x)
    ax2.set_xticklabels(methods)
    ax2.legend()
    ax2.set_ylim(0, 100)

    plt.tight_layout()
    plt.savefig('paper/figures/main_results.pdf', dpi=300, bbox_inches='tight')
    plt.close()
    print("Created: paper/figures/main_results.pdf")


def create_ablation_figure():
    """Create ablation study bar chart."""
    fig, ax = plt.subplots(figsize=(8, 4))

    # Data
    configs = ['Full', 'w/o Hard-\nsafe', 'w/o Ranked\ncandidates', 'w/o Point\nrepair', 'w/o EGHC\nadj.']
    rsr = [67.4, 58.3, 62.0, 60.0, 65.0]
    ssr = [60.1, 47.7, 54.0, 50.0, 58.0]

    x = np.arange(len(configs))
    width = 0.35

    bars1 = ax.bar(x - width/2, rsr, width, label='RSR', color='#3498db')
    bars2 = ax.bar(x + width/2, ssr, width, label='SSR', color='#e67e22')

    ax.set_ylabel('Score (%)')
    ax.set_title('Ablation Study')
    ax.set_xticks(x)
    ax.set_xticklabels(configs)
    ax.legend()
    ax.set_ylim(40, 75)

    # Add value labels
    for bar in bars1:
        height = bar.get_height()
        ax.annotate(f'{height:.1f}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom', fontsize=9)

    for bar in bars2:
        height = bar.get_height()
        ax.annotate(f'{height:.1f}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom', fontsize=9)

    plt.tight_layout()
    plt.savefig('paper/figures/ablation.pdf', dpi=300, bbox_inches='tight')
    plt.close()
    print("Created: paper/figures/ablation.pdf")


def create_route_distribution_figure():
    """Create route distribution pie charts."""
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))

    # Data (approximate from UHS1 results)
    subsets = ['Easy', 'Medium', 'Hard']
    routes = {
        'Easy': [70, 25, 5],  # direct, target_first, blocker_first
        'Medium': [30, 50, 20],
        'Hard': [10, 30, 60],
    }
    colors = ['#2ecc71', '#f39c12', '#e74c3c']

    for ax, subset in zip(axes, subsets):
        data = routes[subset]
        labels = ['direct', 'target_first', 'blocker_first']
        ax.pie(data, labels=labels, colors=colors, autopct='%1.0f%%', startangle=90)
        ax.set_title(f'{subset} Scenes')

    plt.suptitle('Route Distribution by Difficulty', y=1.02)
    plt.tight_layout()
    plt.savefig('paper/figures/route_distribution.pdf', dpi=300, bbox_inches='tight')
    plt.close()
    print("Created: paper/figures/route_distribution.pdf")


if __name__ == '__main__':
    create_main_results_figure()
    create_ablation_figure()
    create_route_distribution_figure()
    print("\nAll figures created successfully!")
