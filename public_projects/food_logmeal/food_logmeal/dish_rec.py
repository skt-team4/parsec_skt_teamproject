import json
import sys
from common import detect_dishes, save_result

def main(image_path=None):
    # Detect dishes
    if image_path:
        result = detect_dishes(image_path)
    else:
        result = detect_dishes()
    
    # Save results
    output_file = save_result(result, 'result/dish', 'dish_result')
    
    print(f"Results saved to: {output_file}")
    
    # Print image ID for use in other scripts
    if 'imageId' in result:
        print(f"Image ID: {result['imageId']}")
        print("\nYou can use this Image ID with ing_info.py or nut_info.py:")
        print(f"  python ing_info.py {result['imageId']}")
        print(f"  python nut_info.py {result['imageId']}")
    
    print("\nSegmentation results:")
    if "segmentation_results" in result:
        print(json.dumps(result["segmentation_results"], indent=2))
    
    return result.get('imageId')

if __name__ == "__main__":
    image_path = sys.argv[1] if len(sys.argv) > 1 else None
    main(image_path)