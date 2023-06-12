"use client";

import classNames from "classnames";
import { useEffect, useState } from "react";

export default function Header() {
    const baseClasses = classNames(
        "transition-[height] duration-200 border-b border-b-black fixed top-0 left-0 w-full z-[100] bg-header-gray flex justify-center"
    );
    const stdClasses = `${baseClasses} h-[50px]`,
        fullClasses = `${baseClasses} h-[120px]`;

    const [classes, setClasses] = useState<string>(fullClasses);

    const updateClasses = () => {
        if (window.scrollY <= 50) {
            setClasses(fullClasses);
        } else {
            setClasses(stdClasses);
        }
    };

    useEffect(() => {
        updateClasses();
        document.addEventListener("scroll", (e) => updateClasses());
    }, []);

    return (
        <header id="site_header" className={classes}>
            <div className="max-w-screen-xl w-full">Header</div>
        </header>
    );
}
