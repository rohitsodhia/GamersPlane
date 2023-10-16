import styles from "./Select.module.css";
import { useState } from "react";

interface SelectProps {
    combobox?: boolean;
    placeholder?: string;
    values: { [key: string | number]: string | number } | (string | number)[];
    onChange: (value: any) => any;
}

export default function Select({
    combobox = false,
    placeholder,
    values,
    onChange,
}: SelectProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [value, setValue] = useState<string | number>("");

    const toggleOpen = () => {
        setIsOpen(!isOpen);
    };

    const valuesArray = Array.isArray(values);
    let options = (valuesArray ? values : Object.entries(values)).map(
        (value, i) => {
            let key: string | number = i;
            let dispValue: string | number;
            if (!valuesArray) {
                [key, dispValue] = value as [string, string | number];
            } else {
                dispValue = value as string | number;
            }
            const onOptionClick = () => {
                const newValue = valuesArray
                    ? (dispValue as string | number)
                    : key;
                setValue(newValue);
                onChange(newValue);
            };
            return (
                <div key={dispValue} onClick={onOptionClick}>
                    {dispValue}
                </div>
            );
        }
    );

    const onValueChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const newValue = e.target.value;
        setValue(newValue);
        onChange(newValue);
    };

    return (
        <div
            className={`${styles.select} ${isOpen && styles.open}`}
            onClick={toggleOpen}
        >
            <div className={styles.display}>&nbsp;</div>
            <input
                type="text"
                disabled
                value={
                    valuesArray ? value : value in values ? values[value] : ""
                }
                onChange={onValueChange}
            />
            <div className={`${styles.options}`}>{options}</div>
        </div>
    );
}
