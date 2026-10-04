import { useEffect, useId, useState } from "react";
import { inventoryApi, trackParts } from "../inventory";

/** Search the installed LDraw library; selected values remain explicit part IDs. */
export default function PartInput({
  value,
  onChange,
  label,
  placeholder = "Part number or description",
}: {
  value: string;
  onChange: (value: string) => void;
  label: string;
  placeholder?: string;
}) {
  const id = useId();
  const [choices, setChoices] = useState<{ id: string; description: string }[]>(
    [],
  );
  useEffect(() => {
    if (value.trim().length < 2) {
      setChoices([]);
      return;
    }
    let active = true;
    const timer = setTimeout(
      () =>
        inventoryApi.find(value).then(
          (result) => {
            if (active) setChoices(result.parts);
          },
          () => {
            if (active) setChoices([]);
          },
        ),
      300,
    );
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [value]);
  return (
    <>
      <input
        aria-label={label}
        placeholder={placeholder}
        value={value}
        maxLength={80}
        list={id}
        onChange={(e) => {
          onChange(e.target.value);
          trackParts("inventory_part_search_changed");
        }}
      />
      <datalist id={id}>
        {choices.map((part) => (
          <option key={part.id} value={part.id.replace(/\.dat$/, "")}>
            {part.description}
          </option>
        ))}
      </datalist>
    </>
  );
}
