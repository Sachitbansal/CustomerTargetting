import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src import pathway_pipeline

if __name__ == '__main__':
    product_type = sys.argv[1] if len(sys.argv) > 1 else 'home_loan'
    pathway_license_key = "B4EB1A-A250F6-FF4EF4-2ACD7A-46912D-V3"
    pathway_pipeline.main(product_type, pathway_license_key)
