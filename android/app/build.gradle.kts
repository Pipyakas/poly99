plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.pipyakas.poly99"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.pipyakas.poly99"
        minSdk = 26
        targetSdk = 35
        versionCode = 2
        versionName = "1.1.0"

        val url = (project.findProperty("POLY99_URL") as String?) ?: "https://pipyakas.github.io/poly99/"
        buildConfigField("String", "POLY99_URL", "\"$url\"")
    }

    buildFeatures {
        buildConfig = true
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}
