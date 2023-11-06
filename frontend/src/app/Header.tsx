"use client";

import Nav from "./Nav";
import gp_logo from "/src/images/logo.svg";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

export default function Header() {
    const stdHeaderHeight = 70,
        fullHeaderHeight = 120,
        stdImageHeight = 53,
        fullImageHeight = 100;

    const pathname = usePathname();

    const stdSize = (): boolean =>
        typeof window !== "undefined" &&
        (window.scrollY > 50 || window.innerWidth <= 1024);

    const [headerHeight, setHeaderHeight] = useState<number>(
        stdSize() ? stdHeaderHeight : fullHeaderHeight
    );
    const [imgHeight, setImgHeight] = useState<number>(
        stdSize() ? stdImageHeight : fullImageHeight
    );

    const updateClasses = () => {
        if (stdSize()) {
            setHeaderHeight(stdHeaderHeight);
            setImgHeight(stdImageHeight);
        } else {
            setHeaderHeight(fullHeaderHeight);
            setImgHeight(fullImageHeight);
        }
    };

    useEffect(() => {
        if (pathname === "/") {
            document.addEventListener("scroll", updateClasses);
            window.addEventListener("resize", updateClasses);
        } else {
            document.removeEventListener("scroll", updateClasses);
            window.removeEventListener("resize", updateClasses);
        }
        updateClasses();
    }, [pathname]);

    return (
        <header
            id="site_header"
            className="transition-[height] fixed top-0 left-0 w-full z-[100] bg-header-gray shadow-[0_1px_20px_1px_#777] px-4 py-2"
            style={{ height: `${headerHeight}px` }}
        >
            <div className="flex justify-center items-center w-full max-w-screen-xl mx-auto">
                <Link
                    href="/"
                    className="transition-[height] relative w-[250px]"
                    style={{ height: `${imgHeight}px` }}
                >
                    <Image
                        className="object-contain object-left-top"
                        src={gp_logo}
                        alt="Gamers' Plane Logo"
                        fill={true}
                    />
                </Link>
                <Nav />
            </div>
        </header>
    );
}
