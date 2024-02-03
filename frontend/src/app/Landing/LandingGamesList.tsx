"use client";

import Headerbar from "@/components/Headerbar";
import { Combobox, ComboboxOption } from "@/components/ui/Combobox";
import { useState } from "react";

export default function LandingGamesList() {
    const [selectedSystem, setSelectedSystem] = useState("");
    const [query, setQuery] = useState("");

    const systems = [
        { id: 1, name: "apple" },
        { id: 2, name: "banana" },
        { id: 3, name: "blueberry" },
        { id: 4, name: "grapes" },
        { id: 5, name: "pineapple" },
    ];
    // const selectItems = systems.map((system) => (
    // ));

    const getGames = () => {};

    return (
        <div className="flex flex-col bg-white max-w-[960px] mx-3 md:mx-auto p-2">
            <div className="box-border">
                <Headerbar className="text-center">Latest Games</Headerbar>
                <div className="hb-container box-border border-x-2 border-b-2 border-neutral-350 p-4">
                    <Combobox
                        value={selectedSystem}
                        onChange={(system) => setSelectedSystem(system)}
                        displayValue={(system: string) => system}
                        query={query}
                        onQueryChange={setQuery}
                    >
                        {(query.length === 0
                            ? systems
                            : systems.filter((system) =>
                                  system.name
                                      .toLowerCase()
                                      .includes(query.toLowerCase())
                              )
                        ).map((system) => (
                            <ComboboxOption key={system.id} value={system.name}>
                                {system.name}
                            </ComboboxOption>
                        ))}
                    </Combobox>
                </div>
            </div>
        </div>
    );
}
