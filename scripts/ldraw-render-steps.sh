#!/bin/bash

# Render steps independently as images, be it either for a full ldraw model or for individual submodels.
# Required leocad options for this: 

function usage() {

    echo "Usage: $(basename "$0") [options] [mpd,ldr,dat file]"
    echo "  -l, --libpath <path>: Set the Parts Library location to path."
    echo "  -i, --image <basename.ext>: Save a picture for each step in the format specified by ext and exit. Default would be '<basename for the model>.png', or if submodel is present, <basename for the submodel with spaces removed>.png"
    echo "  -f, --from <step>: Set the first step to save pictures. Default is 1."
    echo "  -t, --to <step>: Set the last step to save pictures. If omitted, it will render until the last step for the model, or for the submodel if specified. Default is the last step for model or submodel."
    echo "  -s, --submodel <submodel>: Set the active submodel. Main model only, if missing."
    echo "  --viewpoint <viewpoint>: Set the view to one of the preset viewpoints (front, back, left, right, top, bottom, home). Default is 'home'."
    echo "  --fade-steps: Render parts from prior steps faded."
    echo "  --fade-steps-color <#AARRGGBB>: Renderinng color for prior step parts."
    echo "  --highlight: Highlight parts in the steps they appear."
    echo "  --highlight-color <#AARRGGBB>: Rendering color for highlighted parts."
    echo "  --line-width <width>: Set the width of the edge lines."
}

function num_steps() {
    local model="$1"
    local submodel="$2"

    if [ -z "$submodel" ]; then
        cat "$model" | grep -c "0 STEP"
        return
    fi

    awk -v submodel="$submodel" '
        $0 ~ "0 FILE " submodel {in_block=1; next}
        $0 ~ "0 FILE " && in_block {exit}
        in_block {print}
    ' "$model" | grep -c "0 STEP"

}

if [ "$#" -eq 0 ]; then
    usage
    exit 1
fi

# Parse command line arguments
while [[ "$1" == -* ]]; do
    case "$1" in
        -l|--libpath)
            LIBPATH="$2"
            shift 2
            ;;
        -i|--image)
            IMAGE="$2"
            shift 2
            ;;
        -f|--from)
            FROM="$2"
            shift 2
            ;;
        -t|--to)
            TO="$2"
            shift 2
            ;;
        -s|--submodel)
            SUBMODEL="$2"
            shift 2
            ;;
        --viewpoint)
            VIEWPOINT="$2"
            shift 2
            ;;
        --fade-steps)
            FADE_STEPS=true
            shift
            ;;
        --fade-steps-color)
            FADE_STEPS_COLOR="$2"
            shift 2
            ;;
        --highlight)
            HIGHLIGHT=true
            shift
            ;;
        --highlight-color)
            HIGHLIGHT_COLOR="$2"
            shift 2
            ;;
        --line-width)
            LINE_WIDTH="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Error: Unknown option '$1'"
            usage
            exit 1
            ;;
    esac
done

# model should exist and be readable
if [ ! -r "$1" ]; then
    echo "Error: Model file '$1' does not exist or is not readable."
    exit 1
fi

MODEL="$1"

max_step=$(num_steps "$1" "$SUBMODEL")

# verify that if present, the "from" and "to" steps are within the valid range
if [ -n "$FROM" ] && [ "$FROM" -lt 1 ]; then
    echo "Error: 'from' step must be greater than or equal to 1."
    exit 1
fi

if [ -n "$TO" ] && [ "$TO" -gt "$max_step" ]; then
    echo "Error: 'to' step must be less than or equal to the maximum step ($max_step)."
    exit 1
fi

# "from" step would be 1 except if specified otherwise, "to" step would be the last step except if specified otherwise
FROM="${FROM:-1}"
TO="${TO:-$max_step}"
# Viewpoint would be "home" except if specified otherwise
VIEWPOINT="${VIEWPOINT:-home}"

chosen=${SUBMODEL:-$MODEL}
chosen_noext="${chosen%.*}-${VIEWPOINT}-"

# fix this, output looks like 8448-box1step7.ldr01.png
IMAGE="${IMAGE:-$chosen_noext.png}"
IMAGE="${IMAGE// /_}"

# build command line for rendering the steps with leocad for the given model and options
CMD="leocad"
CMD+=" --image \"$IMAGE\""
CMD+=" --from \"$FROM\""
CMD+=" --to \"$TO\""
CMD+=" --viewpoint \"$VIEWPOINT\""

if [ -n "$LIBPATH" ]; then
    CMD+=" --libpath \"$LIBPATH\""
fi

if [ -n "$SUBMODEL" ]; then
    CMD+=" --submodel \"$SUBMODEL\""
fi

if [ "$FADE_STEPS" = true ]; then
    CMD+=" --fade-steps"
fi

if [ -n "$FADE_STEPS_COLOR" ]; then
    CMD+=" --fade-steps-color \"$FADE_STEPS_COLOR\""
fi

if [ "$HIGHLIGHT" = true ]; then
    CMD+=" --highlight"
fi

if [ -n "$HIGHLIGHT_COLOR" ]; then
    CMD+=" --highlight-color \"$HIGHLIGHT_COLOR\""
fi

if [ -n "$LINE_WIDTH" ]; then
    CMD+=" --line-width \"$LINE_WIDTH\""
fi

CMD+=" \"$1\""

eval "$CMD"

