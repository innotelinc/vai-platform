import { Input } from "@/components/ui/input";
import { TextValue } from "@/types/filters";

interface TextFilterProps {
  value: TextValue;
  onChange: (value: TextValue) => void;
  error?: string;
  placeholder?: string;
  maxLength?: number;
}

export const TextFilter: React.FC<TextFilterProps> = ({
  value,
  onChange,
  error,
  placeholder = "Enter text",
  maxLength,
}) => {
  return (
    <div className="space-y-2">
      <Input
        type="text"
        value={value.value || ""}
        onChange={(e) => onChange({ value: e.target.value })}
        placeholder={placeholder}
        maxLength={maxLength}
        className={error ? "border-red-500" : ""}
      />
      {error && <p className="text-sm text-red-500">{error}</p>}
    </div>
  );
};
