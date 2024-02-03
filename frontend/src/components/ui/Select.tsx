import styles from "./Select.module.css";
import { KeyboardEvent, useState } from "react";

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
    const valuesArray = Array.isArray(values);
    const [isOpen, setIsOpen] = useState(false);
    const [value, setValue] = useState<string | number>("");
    const [inputValue, setInputValue] = useState<string>("");
    const [filteredValues, setFilteredValue] = useState<typeof values>(values);

    const toggleOpen = () => {
        setIsOpen(!isOpen);
    };

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
                setInputValue(dispValue.toString());
                onChange(newValue);
            };
            return (
                <div key={dispValue} onClick={onOptionClick}>
                    {dispValue}
                </div>
            );
        }
    );

    const onInputValueChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const newValue = e.target.value;
        setInputValue(newValue);
    };
    const onInputKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
        console.log(e.key);
        if (e.key === "ArrowDown") {
        } else if (e.key === "ArrowUp") {
        } else if (e.key === "Enter") {
        }
    };

    return (
        <div
            className={`${styles.select} ${isOpen && styles.open}`}
            onClick={toggleOpen}
            onKeyDown={onInputKeyDown}
            tabIndex={combobox ? -1 : 0}
        >
            <div className={styles.display}>&nbsp;</div>
            <input
                type="text"
                disabled={!combobox}
                value={inputValue}
                onFocus={() => setIsOpen(true)}
                onChange={onInputValueChange}
            />
            <div className={`${styles.options}`}>{options}</div>
        </div>
    );
}
