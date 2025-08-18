import json
import sys
from common import detect_dishes, get_ingredients, save_result

def main(image_id=None, image_path=None):
    # If no image_id provided, detect dishes first
    if not image_id:
        print("No image ID provided, detecting dishes first...")
        dish_result = detect_dishes(image_path) if image_path else detect_dishes()
        image_id = dish_result.get('imageId')
        if not image_id:
            print("Error: Could not get image ID from dish detection")
            return
        print(f"Got image ID: {image_id}")
    
    # Get ingredients information
    result = get_ingredients(image_id)
    
    # Save results
    output_file = save_result(result, 'result/ing', 'ingredients_result')
    
    print(f"Results saved to: {output_file}")
    print(f"Image ID used: {image_id}")
    print("\nIngredients information:")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # First argument is image_id
        image_id = sys.argv[1]
        main(image_id=image_id)
    elif len(sys.argv) > 2:
        # If two arguments, second is image path
        main(image_path=sys.argv[2])
    else:
        # No arguments, will use default image
        main()