import { Combobox as HeadlessCombobox, Transition } from "@headlessui/react";
import { ReactNode, useState } from "react";
import { HiChevronUpDown } from "react-icons/hi2";

export function ComboboxOption({
    value,
    children,
}: {
    value: any;
    children: ReactNode;
}) {
    return (
        <HeadlessCombobox.Option value={value}>
            {({ active, selected }) => (
                <div
                    className={`relative cursor-default select-none px-4 py-2 ${
                        active ? "bg-red-100" : "text-gray-900"
                    }`}
                >
                    {children}
                </div>
            )}
        </HeadlessCombobox.Option>
    );
}

export function Combobox<T>({
    value,
    onChange,
    displayValue,
    query,
    onQueryChange,
    customValueFormat,
    children,
}: {
    value: T;
    onChange: (value: T) => void;
    displayValue: (item: T) => string;
    query: string;
    onQueryChange: (value: string) => void;
    customValueFormat?: T;
    children: ReactNode;
}) {
    return (
        <HeadlessCombobox value={value} onChange={onChange} nullable immediate>
            <div className="relative w-72">
                <div className="relative">
                    <HeadlessCombobox.Input
                        onChange={(event) => onQueryChange(event.target.value)}
                        displayValue={displayValue}
                        className="w-full rounded-lg border-gp-red border py-2 pl-3 pr-10 focus:ring-0 focus:outline-none bg-white focus-visible:ring-1 focus-visible:ring-gp-red/75 focus-visible:ring-offset-1 focus-visible:ring-offset-red-300"
                        autoComplete="off"
                    />
                    <HeadlessCombobox.Button className="absolute inset-y-0 right-0 flex items-center pr-2">
                        <HiChevronUpDown
                            className="h-5 w-5 text-black"
                            aria-hidden="true"
                        />
                    </HeadlessCombobox.Button>
                </div>
                <Transition
                    enter="transition duration-100 ease-out"
                    enterFrom="transform scale-95 opacity-0"
                    enterTo="transform scale-100 opacity-100"
                    leave="transition duration-75 ease-out"
                    leaveFrom="transform scale-100 opacity-100"
                    leaveTo="transform scale-95 opacity-0"
                >
                    <HeadlessCombobox.Options className="absolute max-h-60 w-full overflow-auto rounded-md bg-white mt-1 text-base focus:outline-none">
                        {children}
                        {query.length > 0 && (
                            <ComboboxOption value={customValueFormat ?? query}>
                                Create &quot;{query}&quot;
                            </ComboboxOption>
                        )}
                    </HeadlessCombobox.Options>
                </Transition>
            </div>
        </HeadlessCombobox>
    );
}
