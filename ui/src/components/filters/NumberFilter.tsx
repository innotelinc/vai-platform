import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NumberValue } from "@/types/filters";

interface NumberFilterProps {
  value: NumberValue;
  onChange: (value: NumberValue) => void;
  error?: string;
  placeholder?: string;
  min?: number;
  max?: number;
  step?: number;
}

export const NumberFilter: React.FC<NumberFilterProps> = ({
  value,
  onChange,
  error,
  placeholder = "Enter value",
  min,
  max,
  step = 1,
}) => {
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    if (newValue === '') {
      onChange({ value: null });
    } else {
      const num = parseInt(newValue, 10);
      if (!isNaN(num)) {
        onChange({ value: num });
      }
    }
  };

  return (
    <div className="space-y-2">
      <div className="space-y-2">
        <Label htmlFor="number-filter">Value</Label>
        <Input
          id="number-filter"
          type="number"
          value={value.value ?? ''}
          onChange={handleChange}
          placeholder={placeholder}
          min={min}
          max={max}
          step={step}
          className={error ? "border-red-500" : ""}
        />
      </div>
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
};
