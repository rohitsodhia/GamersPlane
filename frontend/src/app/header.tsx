"use client";

import Nav from "./nav";
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
    const [headerHeight, setHeaderHeight] = useState<number>(
        pathname !== "/" ? stdHeaderHeight : fullHeaderHeight
    );
    const [imgHeight, setImgHeight] = useState<number>(
        pathname !== "/" ? stdImageHeight : fullImageHeight
    );

    const updateClasses = () => {
        if (window.scrollY <= 50) {
            setHeaderHeight(fullHeaderHeight);
            setImgHeight(fullImageHeight);
        } else {
            setHeaderHeight(stdHeaderHeight);
            setImgHeight(stdImageHeight);
        }
    };

    useEffect(() => {
        if (pathname === "/") {
            updateClasses();
            document.addEventListener("scroll", updateClasses);
        } else {
            setHeaderHeight(stdHeaderHeight);
            document.removeEventListener("scroll", updateClasses);
        }
    }, [pathname]);

    return (
        <header
            id="site_header"
            className="transition-[height] border-b border-b-black fixed top-0 left-0 w-full z-[100] bg-header-gray shadow-[0_1px_20px_1px_#777] px-4 py-2"
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
