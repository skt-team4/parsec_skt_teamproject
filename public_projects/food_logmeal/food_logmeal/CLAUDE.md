# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a food image analysis application that uses the LogMeal API to analyze food images. The project performs three types of analysis:
- **Dish Recognition**: Detects and segments individual dishes in food images
- **Ingredient Analysis**: Identifies ingredients in detected dishes  
- **Nutritional Information**: Provides nutritional data for food items

## Commands

### Running the Scripts
```bash
# Run dish recognition
python dish_rec.py

# Run ingredient analysis (requires imageId from dish recognition)
python ing_info.py

# Run nutritional analysis (requires imageId from dish recognition)
python nut_info.py
```

### Installing Dependencies
```bash
pip install requests
```

## Architecture

### API Integration Flow
1. `dish_rec.py` processes images from `images/` folder through LogMeal's dish detection API
2. The returned `imageId` is used by both `ing_info.py` and `nut_info.py` for further analysis
3. Results are intended to be saved in corresponding `result/` subdirectories (dish/, ing/, nut/)

### Key Implementation Details
- **Authentication**: All scripts use bearer token authentication with LogMeal API
- **Image Processing**: Currently hardcoded to process `images/sample_food.jpg`
- **API Endpoints**:
  - Dish Detection: `https://api.logmeal.com/v2/image/segmentation/complete/v1.0`
  - Ingredient Info: `https://api.logmeal.com/v2/recipe/ingredients/v1.0`
  - Nutritional Info: `https://api.logmeal.com/v2/recipe/nutritional-info/v1.0`

### Current Limitations
- Scripts don't currently save output to result directories
- imageId needs to be manually transferred between scripts
- No error handling for API failures
- API token is hardcoded in each file

## Important Considerations

When modifying this codebase:
1. **API Token Security**: Consider moving the API token to environment variables or a config file
2. **Output Implementation**: The scripts print JSON responses but don't save them - implement file writing to `result/` directories when needed
3. **imageId Handling**: Consider implementing a workflow that automatically passes imageId between the analysis steps
4. **Error Handling**: Add try-except blocks for API calls and file operations